from django.contrib import admin

from reports.models import Report, Prompt


# Register your models here.


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['task_id','questionnaire_id','status',]


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ['id']