# users/utils/otp.py

import random
from django.core.cache import cache


class OTPService:

    @staticmethod
    def generate_otp():
        # return str(random.randint(10000, 99999))
        return "12345"

    @staticmethod
    def save_otp(phone, otp, ttl=120):
        """
        ttl = 2 minutes
        """
        cache.set(f"otp:{phone}", otp, ttl)

    @staticmethod
    def get_otp(phone):
        return cache.get(f"otp:{phone}")

    @staticmethod
    def clear_otp(phone):
        cache.delete(f"otp:{phone}")
