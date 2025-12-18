from rest_framework import serializers

import reports.serializers
# from questionnaires.models import Option as Option
# from questionnaires.models import Question as Question
# from questionnaires.models import QuestionType as QuestionType
from questionnaires.models import Questionnaire as Questionnaire


# class OptionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Option
#         fields = ['name', 'text', 'description','value']
#
#
# class QuestionSerializer(serializers.ModelSerializer):
#     questionKey = serializers.SerializerMethodField()
#     type = serializers.SerializerMethodField()
#     required = serializers.SerializerMethodField()
#     optionsKeys = serializers.SerializerMethodField()
#     multipleSelect = serializers.SerializerMethodField()
#     placeholderKey = serializers.SerializerMethodField()
#     followUp = serializers.SerializerMethodField()
#
#     class Meta:
#         model = Question
#         fields = [
#             "id",
#             "questionKey",
#             "type",
#             "required",
#             "optionsKeys",
#             "multipleSelect",
#             "placeholderKey",
#             "followUp"
#         ]
#
#     def get_questionKey(self, obj):
#         return f"questions.{obj.name}"
#
#     def get_type(self, obj):
#         return "number" if obj.question_type == QuestionType.OPEN_ENDED else "select"
#
#     def get_required(self, obj):
#         return True
#
#     def get_multipleSelect(self, obj):
#         return False
#
#     def get_placeholderKey(self, obj):
#         return None
#
#     def get_optionsKeys(self, obj):
#         return [f"options.{o.name}" for o in obj.options.all()]
#
#     def get_followUp(self, obj):
#         deps = obj.dependencies.all()
#         if not deps:
#             return None
#         return [
#             {
#                 "dependsOn": f"questions.{d.depends_on.name}",
#                 "optionValue": d.option.value if d.option else None
#             }
#             for d in deps
#         ]
#
#
#     def get_questionKey(self, obj):
#         return f"questions.{obj.name}"
#
#     def get_type(self, obj):
#         return "number" if obj.question_type == QuestionType.OPEN_ENDED else "select"
#
#     def get_optionsKeys(self, obj):
#         return [f"options.{o.name}" for o in obj.options.all()]
#
#     def get_followUp(self, obj):
#         deps = obj.dependencies.all()
#         if not deps:
#             return None
#
#         return [
#             {
#                 "dependsOn": f"questions.{d.depends_on.name}",
#                 "optionValue": d.option.value if d.option else None
#             }
#             for d in deps
#         ]
#
#
# class AnswerCreateItemSerializer(serializers.Serializer):
#     question = serializers.CharField()
#     option = serializers.CharField(required=False, allow_null=True)
#     text_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#
# class AnswerCreateSerializer(serializers.Serializer):
#     answers = AnswerCreateItemSerializer(many=True)



class QuestionnaireListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questionnaire
        fields = [
            'id',
            'user',
            'created_at',
            'is_paid',
            'is_reported',
        ]

class QuestionnaireSerializer(serializers.ModelSerializer):
    report = reports.serializers.ReportSerializer(read_only=True)

    class Meta:
        model = Questionnaire
        fields = [
            'id',
            'user',
            'created_at',
            'is_paid',
            'is_reported',
            'report'
            , 'question_answer'
        ]

class QuestionnaireCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questionnaire
        fields = ['id', 'user', 'created_at', 'is_paid', 'is_reported', 'question_answer']
        read_only_fields = ['id', 'created_at', 'is_paid', 'is_reported']
