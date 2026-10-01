import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class SMSDeliveryError(Exception):
    pass


class SMSService:
    @staticmethod
    def send_sms(phone, message):
        if settings.SMS_BACKEND == 'console':
            if not settings.DEBUG:
                raise SMSDeliveryError('Console SMS backend is disabled in production')
            logger.info('[development SMS] recipient=%s message=%s', phone, message)
            return

        if not settings.SMS_API_URL:
            raise SMSDeliveryError('SMS provider is not configured')

        headers = {'Accept': 'application/json'}
        if settings.SMS_API_KEY:
            headers['Authorization'] = f'Bearer {settings.SMS_API_KEY}'

        try:
            response = requests.post(
                settings.SMS_API_URL,
                json={'phone': phone, 'message': message},
                headers=headers,
                timeout=settings.SMS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.exception('SMS delivery failed for recipient ending in %s', phone[-4:])
            raise SMSDeliveryError('Could not deliver verification code') from exc
