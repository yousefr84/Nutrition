from django.urls import path

from users.views import (
    SendOTPView,
    VerifyOTPView,
    CompleteProfileView, RefreshTokenView
)

urlpatterns = [
    path("auth/send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("auth/complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="token-refresh")
]
