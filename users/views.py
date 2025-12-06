# users/views/auth.py

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import CustomUser
from users.serializers import CompleteProfileSerializer
from users.serializers import SendOTPSerializer
from users.serializers import VerifyOTPSerializer, PublicUserSerializer
from users.utils.otp import OTPService
from users.utils.sms_service import SMSService


class SendOTPView(APIView):
    """
    POST /api/auth/send-otp/
    """

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']

        # چک کنیم کاربر وجود دارد یا نه
        user_exists = CustomUser.objects.filter(phone=phone).exists()

        # OTP تولید
        otp = OTPService.generate_otp()
        OTPService.save_otp(phone, otp)

        # ارسال SMS
        SMSService.send_sms(phone, f"Your verification code is: {otp}")

        return Response(
            {
                "detail": "OTP sent successfully",
                "exists": user_exists
            },
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    """
    POST /api/auth/verify-otp/
    body: { "phone": "09121234567", "code": "123456" }

    Steps:
    - validate input
    - check OTP from cache
    - if ok: clear otp, get_or_create user
    - return user info + tokens (access, refresh)
    """

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        # گرفتن OTP از کش
        saved_otp = OTPService.get_otp(phone)
        if not saved_otp:
            return Response({"detail": "OTP expired or not found"}, status=status.HTTP_401_UNAUTHORIZED)

        if str(saved_otp) != str(code):
            return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        # OTP درست است — پاکش می‌کنیم
        OTPService.clear_otp(phone)

        # درون تراکنش کاربر را بگیریم یا بسازیم
        with transaction.atomic():
            user, created = CustomUser.objects.get_or_create(
                phone=phone,
                defaults={"first_name": "", "last_name": ""},
            )
            # اگر لازم است تنظیمات اضافی انجام شود، اینجا بزنید.
            # توجه: create_user از UserManager ممکنه set_unusable_password رو انجام بده.
            # اگر کاربر تازه ساخته شد و لازم داری کاری پس از ساخت انجام شود، اینجا انجام بده.

        # ایجاد JWT (access + refresh)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        user_data = PublicUserSerializer(user).data

        return Response(
            {
                "detail": "OTP verified successfully",
                "user": user_data,
                "tokens": {
                    "access": access_token,
                    "refresh": refresh_token
                },
                "is_new": created
            },
            status=status.HTTP_200_OK
        )


class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user  # از توکن میاد

        serializer = CompleteProfileSerializer(
            user, data=request.data, partial=False
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "status": "completed",
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_200_OK
        )
