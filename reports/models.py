from django.db import models

from questionnaires.models import Questionnaire


# Create your models here.
class Report(models.Model):
    questionnaire = models.OneToOneField(Questionnaire, on_delete=models.CASCADE, related_name='report')
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finish = models.DateTimeField(blank=True, null=True)
    task_id = models.CharField(max_length=255, blank=True, null=True)


class Prompt(models.Model):
    text = models.TextField()

    def __str__(self):
        return f'prompt number: {self.id + 1}'
