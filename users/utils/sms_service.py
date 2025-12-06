# users/services/sms_service.py

class SMSService:

    @staticmethod
    def send_sms(phone, message):
        """
        اینجا میتونه Kavenegar / Ghasedak / SMS.ir باشه
        فعلاً فقط Mock می‌ذاریم
        """
        print(f"[SMS] To: {phone} | Message: {message}")
        return True
