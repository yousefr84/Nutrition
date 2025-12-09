# users/auth.py
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """
    خواندن access token از کوکی 'access_token' و اعتبارسنجی با SimpleJWT.
    اگر توکنی نباشد None برمی‌گرداند تا DRF بقیه‌ی authentication classes را امتحان کند.
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get("access_token")
        if not raw_token:
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception as exc:
            # در صورت نامعتبر بودن توکن، None برمی‌گردانیم تا در نهایت
            # درخواست غیرمجاز شود (401) توسط DRF
            return None
