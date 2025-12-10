from django.db import models

import users.models as users


# Create your models here.


class Questionnaire(models.Model):
    user = models.ForeignKey(users.CustomUser, on_delete=models.SET_NULL, null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)


class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = 'MC', 'Multiple Choice'
    OPEN_ENDED = 'OE', 'Open Ended'


class Question(models.Model):
    # subdomain = models.ForeignKey(SubDomain, on_delete=models.CASCADE, related_name='questions')
    name = models.CharField(max_length=50, unique=True)  # e.g., q1_s1_d1
    text = models.TextField()  # Question text
    link = models.URLField(blank=True, null=True)
    num_of_question = models.IntegerField()
    all_questions = models.IntegerField()
    question_type = models.CharField(
        max_length=2,
        choices=QuestionType.choices,
        default=QuestionType.MULTIPLE_CHOICE
    )

    def __str__(self):
        return f"{self.name}"


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    name = models.CharField(max_length=50)  # e.g., a1_q1_s1_d1
    text = models.TextField()  # Option text
    value = models.PositiveSmallIntegerField(default=0)  # Option number (1, 2, 3, 4)
    description = models.TextField()

    class Meta:
        unique_together = ('question', 'value')

    def __str__(self):
        return f"{self.name} ({self.value})"


class QuestionDependency(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='dependencies')
    depends_on = models.ForeignKey(Question, on_delete=models.CASCADE)
    option = models.ForeignKey(Option, null=True, blank=True, on_delete=models.CASCADE)


class Answer(models.Model):
    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    option = models.ForeignKey(Option, on_delete=models.CASCADE, blank=True, null=True)
    answered_at = models.DateTimeField(auto_now_add=True)
    text_answer = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('questionnaire', 'question')

    def clean(self):
        from django.core.exceptions import ValidationError
        # اطمینان از اینکه برای سوالات چهارگزینه‌ای فقط option پر شود و برای تشریحی فقط text_answer
        if self.question.question_type == QuestionType.MULTIPLE_CHOICE and not self.option:
            raise ValidationError("Multiple choice questions require an option.")
        if self.question.question_type == QuestionType.OPEN_ENDED and not self.text_answer:
            raise ValidationError("Open-ended questions require a text answer.")
        if self.question.question_type == QuestionType.MULTIPLE_CHOICE and self.text_answer:
            raise ValidationError("Multiple choice questions cannot have a text answer.")
        if self.question.question_type == QuestionType.OPEN_ENDED and self.option:
            raise ValidationError("Open-ended questions cannot have an option.")

    def save(self, *args, **kwargs):
        self.full_clean()  # اجرای اعتبارسنجی قبل از ذخیره
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Answer to {self.question} in {self.questionnaire}"
