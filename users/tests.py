from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from users.models import CustomUser
from users.utils.otp import OTPService
from users.utils.sms_service import SMSDeliveryError


@override_settings(
    TEST_OTP_ENABLED=True,
    TEST_OTP_CODE='123456',
    SMS_API_URL='',
    SECURE_SSL_REDIRECT=False,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class OTPTests(APITestCase):
    phone = 'otp-test-invalid'

    def setUp(self):
        cache.clear()
        self.sms = patch('users.views.SMSService.send_sms').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(cache.clear)

    def send(self):
        return self.client.post(reverse('send-otp'), {'phone': self.phone}, format='json')

    def test_test_mode_stores_fixed_code_without_sms(self):
        with patch.object(cache, 'set', wraps=cache.set) as store:
            response = self.send()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'detail': 'OTP sent successfully', 'exists': False})
        self.assertEqual(OTPService.get_otp(self.phone), '123456')
        store.assert_any_call(f'otp:{self.phone}', '123456', 120)
        self.sms.assert_not_called()

    def test_fixed_code_uses_normal_verification(self):
        self.assertEqual(self.send().status_code, 200)
        response = self.client.post(
            reverse('verify-otp'), {'phone': self.phone, 'code': '123456'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['detail'], 'OTP verified successfully')
        self.assertTrue(CustomUser.objects.filter(phone=self.phone).exists())
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        self.assertIsNone(OTPService.get_otp(self.phone))
        self.sms.assert_not_called()

    def test_cooldown_is_preserved(self):
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)
        self.sms.assert_not_called()

    @override_settings(TEST_OTP_ENABLED=False)
    def test_normal_mode_uses_random_code_and_sms(self):
        with patch.object(OTPService, 'generate_otp', return_value='54321') as generate:
            response = self.send()
        self.assertEqual(response.status_code, 200)
        generate.assert_called_once_with()
        self.sms.assert_called_once_with(self.phone, 'Your verification code is: 54321')
        self.assertEqual(OTPService.get_otp(self.phone), '54321')

    @override_settings(TEST_OTP_ENABLED=False)
    def test_sms_failure_preserves_error_and_clears_cooldown(self):
        self.sms.side_effect = SMSDeliveryError('SMS provider is not configured')
        response = self.send()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {'detail': 'SMS provider is not configured'})
        self.assertIsNone(cache.get(f'otp:cooldown:{self.phone}'))
        self.assertIsNone(OTPService.get_otp(self.phone))
