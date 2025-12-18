from django.urls import path

from questionnaires.views import QuestionnaireCreateAPIView, \
    QuestionnaireListAPIView, QuestionnaireDetailAPIView

urlpatterns = [
    # path('questions/', QuestionListAPIView.as_view(), name='question-list'),
    path('questionnaires/create/', QuestionnaireCreateAPIView.as_view()),
    path('questionnaires/list/', QuestionnaireListAPIView.as_view()),
    # path(
    #     'questionnaires/<int:questionnaire_id>/answers/',
    #     QuestionnaireSubmitAnswersAPIView.as_view(),
    #     name='questionnaire-submit-answers'
    # ),
    path('questionnaires/<int:pk>/', QuestionnaireDetailAPIView.as_view(), name='questionnaire-detail'),

]
