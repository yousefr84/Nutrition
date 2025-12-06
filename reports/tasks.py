import logging
from typing import Dict, List, Any

from celery import shared_task, chord
from django.db import transaction
from django.utils import timezone

from questionnaires.models import Questionnaire
from reports.models import Report, Prompt
# این‌ها مثل نسخه اصلی ثابت می‌مانند و از کد قبلی‌ات می‌گیری

logger = logging.getLogger(__name__)
import openai


logger = logging.getLogger(__name__)


# ----------------------------
# helpers
# ----------------------------

def _log_delivery(self, title: str, extra: Dict[str, Any] = None):
    """Log routing/delivery info to debug queue/routing issues."""
    req = getattr(self, "request", None)
    di = getattr(req, "delivery_info", {}) if req else {}
    info = {
        "task": getattr(req, "task", None),
        "id": getattr(req, "id", None),
        "root_id": getattr(req, "root_id", None),
        "parent_id": getattr(req, "parent_id", None),
        "group": getattr(req, "group", None),
        "chord": getattr(req, "chord", None),
        "hostname": getattr(req, "hostname", None),
        "retries": getattr(req, "retries", None),
        "queue": di.get("routing_key") or di.get("queue"),
        "exchange": di.get("exchange"),
        "consumer_tag": di.get("consumer_tag"),
    }
    if extra:
        info.update(extra)
    logger.info(f"[delivery] {title} :: {info}")


# ----------------------------
# OpenAI helper (env-driven)
# ----------------------------

def openAI(prompt, rule):
    client = openai.OpenAI(api_key='sk-2331fea2a1244273b5179bb4faf8f3c6', base_url="https://api.deepseek.com")
    try:
        response = client.chat.completions.create(
            model='deepseek-reasoner',
            temperature=0.3,
            messages=[
                {"role": "system", "content": rule},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise Exception("Failed to generate report from OpenAI due to API error")
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI call: {str(e)}")
        raise Exception("Failed to generate report from OpenAI")


# ================================
#   Subtask → اجرا برای هر Prompt
# ================================
@shared_task(
    queue="reports",
    bind=True,
    track_started=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    soft_time_limit=60,
    time_limit=180,
)
def run_prompt(self, prompt_id: int, questionnaire_id: int) -> Dict[str, Any]:
    """
    این تسک یک Prompt را می‌گیرد → یک ریکوئست AI اجرا می‌کند → خروجی را برمی‌گرداند
    """
    _log_delivery(self, "run_prompt:start", {"prompt_id": prompt_id})

    try:
        prompt_obj = Prompt.objects.get(id=prompt_id)
    except Prompt.DoesNotExist:
        return {"error": f"Prompt {prompt_id} not found", "prompt_id": prompt_id}

    try:
        questionnaire = Questionnaire.objects.prefetch_related(
            "answers__question", "answers__option"
        ).get(id=questionnaire_id)
    except Questionnaire.DoesNotExist:
        return {"error": f"Questionnaire {questionnaire_id} not found", "prompt_id": prompt_id}

    # -----------------------------
    # ساختن Questions + Answers
    # -----------------------------
    answers = questionnaire.answers.all()

    qa_lines: List[str] = []
    for a in answers:
        q_text = a.question.text if a.question else "unknown question"

        if a.option:
            qa_lines.append(f"{q_text}: {a.option.text}")
        else:
            txt = (a.text_answer or "").strip()
            if txt:
                qa_lines.append(f"{q_text}: {txt}")

    questions_and_answers = "\n".join(qa_lines) if qa_lines else "بدون پاسخ"

    # -----------------------------
    # ساختن Prompt نهایی
    # -----------------------------
    filled_prompt = prompt_obj.text.format(
        questions_and_answers=questions_and_answers
    )

    rule = "You are an expert assistant. Analyze carefully and respond precisely."

    # -----------------------------
    # ارسال request به AI
    # -----------------------------
    try:
        response = openAI(filled_prompt, rule)
    except Exception as e:
        response = f"AI error: {str(e)}"

    return {
        "prompt_id": prompt_id,
        "prompt_text": prompt_obj.text,
        "response": response,
        "filled_prompt": filled_prompt,
    }


# ======================================
#   Callback → بعد از تمام subtaskها
# ======================================
@shared_task(
    queue="reports",
    bind=True,
    track_started=True,
    acks_late=True,
    soft_time_limit=60,
    time_limit=300,
)
def combine_prompt_results(self, results: List[Dict[str, Any]], report_id: int):
    """
    این تسک بعد از اینکه همه prompt ها نتیجه دادند اجرا می‌شود
    """
    _log_delivery(self, "combine_prompt_results:start", {"report_id": report_id})

    try:
        report = Report.objects.get(id=report_id)
    except Report.DoesNotExist:
        logger.error(f"Report {report_id} not found in callback")
        return

    final_result = {
        "generated_at": timezone.now().isoformat(),
        "prompts": results,  # لیست کامل پاسخ‌ها
    }

    with transaction.atomic():
        report.result = final_result
        report.status = "done"
        report.finish = timezone.now()
        report.save(update_fields=["result", "status", "finish"])

    logger.info(f"[combine_prompt_results] Report {report_id} completed")


# ======================================
#   Orchestrator → ساخت chord
# ======================================
@shared_task(
    queue="reports",
    bind=True,
    track_started=True,
    acks_late=True,
    soft_time_limit=30,
    time_limit=120,
)
def generate_report(self, report_id: int):
    """
    orchestrator:
    1) جمع‌آوری promptها
    2) ساخت header (لیست task های موازی)
    3) chord → اجرا برای همه promptها
    4) callback نهایی combine_prompt_results
    """
    _log_delivery(self, "generate_report:start", {"report_id": report_id})

    try:
        report = Report.objects.select_related("questionnaire").get(id=report_id)
    except Report.DoesNotExist:
        logger.error(f"Report {report_id} not found")
        return

    prompts = list(Prompt.objects.all())

    if not prompts:
        report.status = "error"
        report.result = {"error": "No prompts found"}
        report.finish = timezone.now()
        report.save(update_fields=["status", "result", "finish"])
        return

    questionnaire = report.questionnaire

    header = [
        run_prompt.s(p.id, questionnaire.id).set(queue="reports")
        for p in prompts
    ]

    logger.info(f"[generate_report] Running {len(header)} parallel prompts")

    callback = combine_prompt_results.s(report_id).set(queue="reports")

    chord(header)(callback)

    report.status = "processing"
    report.save(update_fields=["status"])

    return {"detail": "Report generation started", "prompts": len(header)}
