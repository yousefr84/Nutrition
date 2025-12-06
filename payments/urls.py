from django.urls import path

from payments.views import PayCheckAPIView, PaymentAPIView, PaymentsView

urlpatterns = [
    path('discount/', PayCheckAPIView.as_view(), name='discount'),
    path('request/', PaymentAPIView.as_view(), name='payment_start'),
    path('payment/verify/', PaymentAPIView.as_view(), name='payment_verify'),
    path('payment/list/', PaymentsView.as_view(), name='payment_list'),
]
