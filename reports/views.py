# Create your views here.
from celery.result import AsyncResult
from django.contrib.auth.models import User

from reports.tasks import generate_report
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from questionnaires.models import Questionnaire
from reports.models import Report
from reports.serializers import ReportSerializer


class StartReportAPIView(APIView):
    def post(self, request, questionnaire_id):
        # چک وجود پرسشنامه
        try:
            questionnaire = Questionnaire.objects.get(id=questionnaire_id, user=request.user)
        except Questionnaire.DoesNotExist:
            return Response(
                {"detail": "Questionnaire not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # اگر گزارش از قبل وجود دارد
        report = getattr(questionnaire, "report", None)

        if report:
            # اگر در حال پردازش است، تکرار نکن
            if report.status in ["processing", "pending"]:
                return Response(
                    {
                        "detail": "Report is already being generated",
                        "report": ReportSerializer(report).data
                    },
                    status=status.HTTP_200_OK
                )
            # اگر done است فعلا اجازه اجرای مجدد نمی‌دهیم (طبق توافق فعلی)
            if report.status == "done":
                return Response(
                    {
                        "detail": "Report already generated",
                        "report": ReportSerializer(report).data
                    },
                    status=status.HTTP_200_OK
                )

        # اگر گزارش وجود ندارد → بساز
        if not report:
            report = Report.objects.create(
                questionnaire=questionnaire,
                status="processing"
            )

        # اجرای تسک
        task = generate_report.delay(report.id)
        report.task_id = task.id
        report.status = "processing"
        report.save()

        return Response(
            {
                "detail": "Report generation started",
                "task_id": report.task_id,
                "report": ReportSerializer(report).data
            },
            status=status.HTTP_202_ACCEPTED
        )


class ReportStatusAPIView(APIView):
    def get(self, request, questionnaire_id):
        # وجود پرسشنامه برای این کاربر؟

        try:
            user = request.user
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            questionnaire = Questionnaire.objects.get(id=questionnaire_id, user=user)
        except Questionnaire.DoesNotExist:
            return Response(
                {"detail": "Questionnaire not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # وجود گزارش
        report = getattr(questionnaire, "report", None)
        if not report:
            return Response(
                {"detail": "Report not requested yet"},
                status=status.HTTP_404_NOT_FOUND
            )

        # اگر هنوز در حال پردازش است
        if report.status in ["pending", "processing"]:
            response = {
                "status": report.status,
                "detail": "Report is still being generated"
            }

            # اگر task_id هست → وضعیت celery را هم اضافه کنیم
            if report.task_id:
                task_result = AsyncResult(report.task_id)
                response["celery_state"] = task_result.state

            return Response(response, status=status.HTTP_200_OK)

        # اگر done شده
        if report.status == "done":
            return Response(
                {
                    "status": "done",
                    "result": report.result
                },
                status=status.HTTP_200_OK
            )

        # اگر error شده
        if report.status == "error":
            return Response(
                {
                    "status": "error",
                    "error": report.result.get("error", "Unknown error")
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
