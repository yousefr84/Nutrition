from django.db import models

# Create your models here.
from django.db import models

from payments.utilitis import generate_unique_pid as generate_unique_pid
from questionnaires.models import Questionnaire as Questionnaire
from users.models import CustomUser as CustomUser


# Create your models here.
class Payment(models.Model):
    price = models.IntegerField()
    questionnaire = models.OneToOneField(Questionnaire, on_delete=models.CASCADE, related_name='payments')
    date = models.DateTimeField(auto_now_add=True)
    pid = models.IntegerField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    successful = models.BooleanField(default=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    description = models.TextField()
    authority = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Payment {self.pid} - {self.price} تومان"

    def save(self, *args, **kwargs):
        if not self.pid:
            self.pid = generate_unique_pid(Payment)
        super().save(*args, **kwargs)


class Discount(models.Model):
    code = models.CharField(max_length=10, unique=True)
    percent = models.IntegerField()
    usage = models.PositiveSmallIntegerField(default=2)

    def __str__(self):
        return self.code


class Price(models.Model):
    price = models.IntegerField()

    def __str__(self):
        return str(self.price)
