# Create your views here.
from django.db import transaction
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.generics import ListAPIView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# from questionnaires.models import Question, Option, Answer,
from questionnaires.models import Questionnaire
# from questionnaires.serializers import AnswerCreateSerializer
# from questionnaires.serializers import QuestionSerializer
from questionnaires.serializers import QuestionnaireCreateSerializer
from questionnaires.serializers import QuestionnaireListSerializer
from questionnaires.serializers import QuestionnaireSerializer


# class QuestionListAPIView(ListAPIView):
#     serializer_class = QuestionSerializer
#     queryset = Question.objects.all().order_by('num_of_question')


class QuestionnaireCreateAPIView(CreateAPIView):
    serializer_class = QuestionnaireCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# class QuestionnaireSubmitAnswersAPIView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request, questionnaire_id):
#         serializer = AnswerCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#
#         answers_data = serializer.validated_data['answers']
#
#         # چک کنیم پرسشنامه واقعا مال همین کاربر باشد
#         try:
#             questionnaire = Questionnaire.objects.get(id=questionnaire_id, user=request.user)
#         except Questionnaire.DoesNotExist:
#             return Response({"error": "Questionnaire not found"}, status=status.HTTP_404_NOT_FOUND)
#
#         # تراکنش اتمیک (یا همه ثبت می‌شوند یا هیچ‌کدام)
#         with transaction.atomic():
#             created_answers = []
#
#             for item in answers_data:
#                 question_name = item['question']
#                 option_name = item.get('option')
#                 text_answer = item.get('text_answer')
#
#                 # 1) بازیابی سوال
#                 try:
#                     question = Question.objects.get(name=question_name)
#                 except Question.DoesNotExist:
#                     return Response({"error": f"Invalid question: {question_name}"}, status=400)
#
#                 # 2) اگر MC باشد → باید option پیدا کنیم
#                 option_obj = None
#                 if question.question_type == "MC":
#                     if not option_name:
#                         return Response(
#                             {"error": f"Question {question_name} requires an option"},
#                             status=400
#                         )
#                     try:
#                         option_obj = Option.objects.get(name=option_name, question=question)
#                     except Option.DoesNotExist:
#                         return Response(
#                             {"error": f"Invalid option for {question_name}: {option_name}"},
#                             status=400
#                         )
#
#                 # 3) ساخت Answer
#                 answer = Answer(
#                     questionnaire=questionnaire,
#                     question=question,
#                     option=option_obj,
#                     text_answer=text_answer
#                 )
#
#                 # clean() مدل اجرا می‌شود
#                 answer.full_clean()
#                 created_answers.append(answer)
#
#             # اگر همه معتبر بودند → ذخیره
#             for ans in created_answers:
#                 ans.save()
#
#         return Response({"message": "Answers submitted successfully"}, status=200)


class QuestionnaireListAPIView(ListAPIView):
    serializer_class = QuestionnaireListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Questionnaire.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class QuestionnaireDetailAPIView(RetrieveAPIView):
    serializer_class = QuestionnaireSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # فقط پرسشنامه‌های همین کاربر
        return Questionnaire.objects.filter(user=self.request.user)
