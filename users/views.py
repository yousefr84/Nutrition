# users/views/auth.py

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from Taghzieh.settings import DEBUG
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
        response = Response(
            {
                "detail": "OTP verified successfully",
                "user": user_data,
                "is_new": created
            },
            status=status.HTTP_200_OK
        )

        # cookie params
        ACCESS_MAX_AGE = 15 * 60  # 15 minutes
        REFRESH_MAX_AGE = 7 * 24 * 60 * 60  # 7 days

        secure_flag = not DEBUG  # در محیط dev ممکنه DEBUG=True باشد؛ در prod حتما True کن

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
            max_age=ACCESS_MAX_AGE,
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=secure_flag,
            samesite="Lax",
            max_age=REFRESH_MAX_AGE,
        )

        return response


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


# users/views.py (اضافه کن)
from rest_framework.permissions import AllowAny
from django.conf import settings


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "Refresh token not provided"}, status=401)

        try:
            # اعتبارسنجی و rotate کردن
            token = RefreshToken(refresh_token)
            user_id = token["user_id"]
            # خارج کردن کاربر از token
            # می‌تونیم user را با id بگیریم:
            from users.models import CustomUser
            try:
                user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                return Response({"detail": "User not found"}, status=404)

            # ایجاد توکن‌های جدید (rotate)
            new_refresh = RefreshToken.for_user(user)
            new_access = str(new_refresh.access_token)
            new_refresh_str = str(new_refresh)

            ACCESS_MAX_AGE = 15 * 60
            REFRESH_MAX_AGE = 7 * 24 * 60 * 60
            secure_flag = not settings.DEBUG

            response = Response({"detail": "Token refreshed"}, status=200)
            response.set_cookie(
                key="access_token",
                value=new_access,
                httponly=True,
                secure=secure_flag,
                samesite="Lax",
                max_age=ACCESS_MAX_AGE,
            )
            response.set_cookie(
                key="refresh_token",
                value=new_refresh_str,
                httponly=True,
                secure=secure_flag,
                samesite="Lax",
                max_age=REFRESH_MAX_AGE,
            )
            return response

        except TokenError:
            return Response({"detail": "Invalid refresh token"}, status=401)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
