from django.contrib import admin

from payments.models import Discount, Price


# Register your models here.



@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ['code','percent','usage']


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ['price']