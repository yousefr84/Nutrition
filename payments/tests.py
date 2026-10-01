from unittest.mock import Mock, patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from payments.models import Discount, Payment, Price
from payments.services import (
    GatewayResult,
    PaymentGatewayTimeout,
    create_gateway_payment,
    verify_gateway_payment,
)
from questionnaires.models import Questionnaire
from users.models import CustomUser


@override_settings(
    SECURE_SSL_REDIRECT=False,
    FRONTEND_BASE_URL='https://frontend.example.com',
    ZARINPAL_STARTPAY_URL='https://gateway.example.com/start',
)
class PaymentAPITests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(phone='+989121111111')
        self.other_user = CustomUser.objects.create_user(phone='+989122222222')
        self.questionnaire = Questionnaire.objects.create(
            user=self.user,
            question_answer=[],
        )
        self.other_questionnaire = Questionnaire.objects.create(
            user=self.other_user,
            question_answer=[],
        )
        self.client.force_authenticate(self.user)

    def test_price_without_configuration_returns_503_instead_of_500(self):
        response = self.client.get('/payments/discount/')

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['detail'], 'Payment price is not configured')

    def test_discount_quote_does_not_consume_usage(self):
        Price.objects.create(price=100_000)
        discount = Discount.objects.create(code='SAVE10', percent=10, usage=2)

        response = self.client.post('/payments/discount/', {'discount_code': 'SAVE10'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['price'], 90_000)
        discount.refresh_from_db()
        self.assertEqual(discount.usage, 2)

    def test_payment_request_validates_payload(self):
        response = self.client.post('/payments/request/', {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('questionnaire_id', response.data)

    def test_payment_request_rejects_questionnaire_owned_by_another_user(self):
        Price.objects.create(price=100_000)

        response = self.client.post(
            '/payments/request/',
            {'questionnaire_id': self.other_questionnaire.id},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('payments.views.create_gateway_payment')
    def test_payment_request_uses_authenticated_user_and_server_price(self, create_payment):
        create_payment.return_value = GatewayResult(code=100, authority='AUTH-123')
        Price.objects.create(price=100_000)
        discount = Discount.objects.create(code='SAVE10', percent=10, usage=2)

        response = self.client.post(
            '/payments/request/',
            {
                'questionnaire_id': self.questionnaire.id,
                'description': 'Nutrition report',
                'discount_code': 'SAVE10',
                # These untrusted legacy fields must be ignored.
                'price': 1,
                'username': self.other_user.phone,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount'], 90_000)
        payment = Payment.objects.get(questionnaire=self.questionnaire)
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.price, 90_000)
        self.assertEqual(payment.authority, 'AUTH-123')
        discount.refresh_from_db()
        self.assertEqual(discount.usage, 1)

    def test_payment_list_only_returns_authenticated_users_payments(self):
        Payment.objects.create(
            questionnaire=self.questionnaire,
            user=self.user,
            price=100_000,
            description='Mine',
        )
        Payment.objects.create(
            questionnaire=self.other_questionnaire,
            user=self.other_user,
            price=100_000,
            description='Not mine',
        )

        response = self.client.get(
            f'/payments/payment/list/?username={self.other_user.phone}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['description'], 'Mine')

    @patch('payments.views.verify_gateway_payment')
    def test_gateway_callback_is_public_and_marks_questionnaire_paid(self, verify_payment):
        verify_payment.return_value = GatewayResult(code=100)
        payment = Payment.objects.create(
            questionnaire=self.questionnaire,
            user=self.user,
            price=100_000,
            description='Nutrition report',
            authority='AUTH-VERIFY',
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(
            '/payments/payment/verify/?Authority=AUTH-VERIFY&Status=OK'
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            response.url,
            f'https://frontend.example.com/main/SuccessfulPayPage?questionnaire_id={self.questionnaire.id}',
        )
        payment.refresh_from_db()
        self.questionnaire.refresh_from_db()
        self.assertTrue(payment.successful)
        self.assertTrue(self.questionnaire.is_paid)


@override_settings(
    ZARINPAL_MERCHANT_ID='test-merchant',
    ZARINPAL_REQUEST_URL='https://gateway.example.com/request',
    ZARINPAL_VERIFY_URL='https://gateway.example.com/verify',
    ZARINPAL_CALLBACK_URL='https://api.example.com/payments/verify/',
    ZARINPAL_TIMEOUT_SECONDS=10,
)
class PaymentGatewayServiceTests(APITestCase):
    @patch('payments.services.requests.post')
    def test_create_payment_parses_v4_response(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {
            'data': {'code': 100, 'authority': 'A000000000000000000000000001'},
            'errors': [],
        }
        post.return_value = response

        result = create_gateway_payment(
            amount=100_000,
            description='Nutrition report',
            phone='+989121111111',
        )

        self.assertEqual(result.code, 100)
        self.assertEqual(result.authority, 'A000000000000000000000000001')
        post.assert_called_once_with(
            'https://gateway.example.com/request',
            json={
                'merchant_id': 'test-merchant',
                'amount': 100_000,
                'callback_url': 'https://api.example.com/payments/verify/',
                'description': 'Nutrition report',
                'metadata': {'mobile': '+989121111111'},
            },
            timeout=10,
        )

    @patch('payments.services.requests.post')
    def test_verify_accepts_already_verified_code(self, post):
        response = Mock(status_code=200)
        response.json.return_value = {'data': {'code': 101}, 'errors': []}
        post.return_value = response

        result = verify_gateway_payment(amount=100_000, authority='AUTH-101')

        self.assertEqual(result.code, 101)

    @patch('payments.services.requests.post')
    def test_gateway_timeout_is_normalized(self, post):
        import requests

        post.side_effect = requests.Timeout()

        with self.assertRaises(PaymentGatewayTimeout):
            create_gateway_payment(
                amount=100_000,
                description='Nutrition report',
                phone='+989121111111',
            )
