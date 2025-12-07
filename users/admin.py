from django.contrib import admin

from users.models import CustomUser


# Register your models here.

@admin.register(CustomUser)
class ModelNameAdmin(admin.ModelAdmin):
    list_display = ['phone']


