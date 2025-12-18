from django.contrib import admin

from questionnaires.models import Questionnaire


# Register your models here.


@admin.register(Questionnaire)
class QuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['user_id','created_at']

# @admin.register(Question)
# class QuestionAdmin(admin.ModelAdmin):
#     list_display = ['name']
#
#
# @admin.register(Option)
# class OptionAdmin(admin.ModelAdmin):
#     list_display = ['name','value']