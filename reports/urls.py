from django.urls import path
from reports.views import StartReportAPIView, ReportStatusAPIView

urlpatterns = [
    path('start/<int:questionnaire_id>/', StartReportAPIView.as_view(), name='report-start'),
    path('status/<int:questionnaire_id>/', ReportStatusAPIView.as_view(), name='report-status'),
]
