from django.urls import path

from payments.views import (
    PayCheckAPIView,
    PaymentRequestAPIView,
    PaymentVerifyAPIView,
    PaymentsView,
)

urlpatterns = [
    path('discount/', PayCheckAPIView.as_view(), name='discount'),
    path('request/', PaymentRequestAPIView.as_view(), name='payment_start'),
    path('payment/verify/', PaymentVerifyAPIView.as_view(), name='payment_verify'),
    path('payment/list/', PaymentsView.as_view(), name='payment_list'),
]
