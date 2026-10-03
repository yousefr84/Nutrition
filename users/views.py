# users/views/auth.py

import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import CustomUser
from users.serializers import CompleteProfileSerializer
from users.serializers import SendOTPSerializer
from users.serializers import VerifyOTPSerializer, PublicUserSerializer
from users.utils.otp import OTPService
from users.utils.sms_service import SMSDeliveryError, SMSService


class SendOTPView(APIView):
    """
    POST /api/auth/send-otp/
    """

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']

        cooldown_key = f'otp:cooldown:{phone}'
        if not cache.add(cooldown_key, '1', timeout=60):
            return Response(
                {'detail': 'Please wait before requesting another code'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # چک کنیم کاربر وجود دارد یا نه
        user_exists = CustomUser.objects.filter(phone=phone).exists()

        if settings.TEST_OTP_ENABLED:
            otp = settings.TEST_OTP_CODE
        else:
            otp = OTPService.generate_otp()
            try:
                SMSService.send_sms(phone, f"Your verification code is: {otp}")
            except SMSDeliveryError as exc:
                cache.delete(cooldown_key)
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        OTPService.save_otp(phone, otp)

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
        attempts_key = f'otp:attempts:{phone}'
        attempts = int(cache.get(attempts_key, 0))
        if attempts >= 5:
            return Response(
                {'detail': 'Too many invalid attempts'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # گرفتن OTP از کش
        saved_otp = OTPService.get_otp(phone)
        if not saved_otp:
            return Response({"detail": "OTP expired or not found"}, status=status.HTTP_401_UNAUTHORIZED)

        if not secrets.compare_digest(str(saved_otp), str(code)):
            cache.set(attempts_key, attempts + 1, timeout=120)
            return Response({"detail": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        # OTP درست است — پاکش می‌کنیم
        OTPService.clear_otp(phone)
        cache.delete(attempts_key)

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
        access_max_age = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
        refresh_max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=access_max_age,
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=refresh_max_age,
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

            access_max_age = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
            refresh_max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

            token.blacklist()

            response = Response({"detail": "Token refreshed"}, status=200)
            response.set_cookie(
                key="access_token",
                value=new_access,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                max_age=access_max_age,
            )
            response.set_cookie(
                key="refresh_token",
                value=new_refresh_str,
                httponly=True,
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                max_age=refresh_max_age,
            )
            return response

        except TokenError:
            return Response({"detail": "Invalid refresh token"}, status=401)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)


class LogoutView(APIView):
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        response = Response({"detail": "Logged out"}, status=200)
        response.delete_cookie(
            "access_token",
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )
        response.delete_cookie(
            "refresh_token",
            samesite=settings.SESSION_COOKIE_SAMESITE,
        )
        return response
