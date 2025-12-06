from rest_framework import serializers

import reports.serializers
from questionnaires.models import Answer as Answer
from questionnaires.models import Option as Option
from questionnaires.models import Question as Question
from questionnaires.models import QuestionType as QuestionType
from questionnaires.models import Questionnaire as Questionnaire


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['name', 'text', 'description','value']


class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    question_type = serializers.ChoiceField(choices=QuestionType.choices)

    class Meta:
        model = Question
        fields = ['name', 'text', 'question_type', 'options', 'link', 'num_of_question', 'all_questions']

    def get_options(self, obj):
        if obj.question_type == QuestionType.MULTIPLE_CHOICE:
            return OptionSerializer(obj.options.all(), many=True).data
        return []


class AnswerCreateItemSerializer(serializers.Serializer):
    question = serializers.CharField()
    option = serializers.CharField(required=False, allow_null=True)
    text_answer = serializers.CharField(required=False, allow_blank=True, allow_null=True)

class AnswerCreateSerializer(serializers.Serializer):
    answers = AnswerCreateItemSerializer(many=True)



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
            'report',
        ]

class QuestionnaireCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Questionnaire
        fields = ['id', 'user', 'created_at', 'is_paid', 'is_reported']
        read_only_fields = ['id', 'created_at', 'is_paid', 'is_reported']
