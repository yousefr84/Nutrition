from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Discount, Payment, Price
from payments.serializers import (
    DiscountCodeSerializer,
    PaymentRequestSerializer,
    PaymentSerializer,
)
from payments.services import (
    PaymentGatewayConfigurationError,
    PaymentGatewayError,
    PaymentGatewayTimeout,
    create_gateway_payment,
    verify_gateway_payment,
)
from questionnaires.models import Questionnaire


def _configured_price():
    return Price.objects.order_by('-id').first()


def _discounted_amount(price: int, discount: Discount | None) -> int:
    if discount is None:
        return price
    percent = min(max(discount.percent, 0), 100)
    return max(price - (price * percent // 100), 0)


def _frontend_redirect(page: str, **query) -> HttpResponseRedirect:
    url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/main/{page}"
    if query:
        url = f'{url}?{urlencode(query)}'
    return HttpResponseRedirect(url)


class PayCheckAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        price = _configured_price()
        if price is None:
            return Response(
                {'detail': 'Payment price is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'price': price.price})

    def post(self, request):
        serializer = DiscountCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        price = _configured_price()
        if price is None:
            return Response(
                {'detail': 'Payment price is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            discount = Discount.objects.get(code=serializer.validated_data['discount_code'])
        except Discount.DoesNotExist:
            return Response(
                {'detail': 'Discount code is invalid'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if discount.usage <= 0:
            return Response(
                {'detail': 'Discount code has expired'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 0 <= discount.percent <= 100:
            return Response(
                {'detail': 'Discount code is misconfigured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({'price': _discounted_amount(price.price, discount)})


class PaymentRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            questionnaire = Questionnaire.objects.get(
                id=data['questionnaire_id'],
                user=request.user,
            )
        except Questionnaire.DoesNotExist:
            return Response(
                {'detail': 'Questionnaire not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if questionnaire.is_paid or Payment.objects.filter(
            questionnaire=questionnaire,
            successful=True,
        ).exists():
            return Response(
                {'detail': 'Questionnaire is already paid'},
                status=status.HTTP_409_CONFLICT,
            )

        configured_price = _configured_price()
        if configured_price is None:
            return Response(
                {'detail': 'Payment price is not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        discount = None
        discount_code = data.get('discount_code')
        if discount_code:
            discount = Discount.objects.filter(code=discount_code, usage__gt=0).first()
            if discount is None:
                return Response(
                    {'detail': 'Discount code is invalid or expired'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not 0 <= discount.percent <= 100:
                return Response(
                    {'detail': 'Discount code is misconfigured'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        amount = _discounted_amount(configured_price.price, discount)
        description = data.get('description') or f'Questionnaire {questionnaire.id}'

        discount_reserved = False
        if discount is not None:
            discount_reserved = bool(
                Discount.objects.filter(pk=discount.pk, usage__gt=0).update(usage=F('usage') - 1)
            )
            if not discount_reserved:
                return Response(
                    {'detail': 'Discount code has expired'},
                    status=status.HTTP_409_CONFLICT,
                )

        if amount == 0:
            with transaction.atomic():
                payment, _ = Payment.objects.update_or_create(
                    questionnaire=questionnaire,
                    defaults={
                        'price': 0,
                        'user': request.user,
                        'description': description,
                        'authority': None,
                        'successful': True,
                    },
                )
                Questionnaire.objects.filter(pk=questionnaire.pk).update(is_paid=True)
            return Response(
                {
                    'status': True,
                    'url': f"{settings.FRONTEND_BASE_URL.rstrip('/')}/result/{questionnaire.id}",
                    'authority': None,
                    'payment_id': payment.id,
                    'amount': 0,
                }
            )

        try:
            gateway = create_gateway_payment(
                amount=amount,
                description=description,
                phone=request.user.phone,
            )
            payment, _ = Payment.objects.update_or_create(
                questionnaire=questionnaire,
                defaults={
                    'price': amount,
                    'user': request.user,
                    'description': description,
                    'authority': gateway.authority,
                    'successful': False,
                },
            )
        except PaymentGatewayConfigurationError as exc:
            if discount_reserved:
                Discount.objects.filter(pk=discount.pk).update(usage=F('usage') + 1)
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except PaymentGatewayTimeout as exc:
            if discount_reserved:
                Discount.objects.filter(pk=discount.pk).update(usage=F('usage') + 1)
            return Response({'detail': str(exc)}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except PaymentGatewayError as exc:
            if discount_reserved:
                Discount.objects.filter(pk=discount.pk).update(usage=F('usage') + 1)
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            if discount_reserved:
                Discount.objects.filter(pk=discount.pk).update(usage=F('usage') + 1)
            raise

        return Response(
            {
                'status': True,
                'url': f"{settings.ZARINPAL_STARTPAY_URL.rstrip('/')}/{gateway.authority}",
                'authority': gateway.authority,
                'payment_id': payment.id,
                'amount': amount,
            },
            status=status.HTTP_200_OK,
        )


class PaymentVerifyAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        authority = request.query_params.get('Authority')
        payment_status = request.query_params.get('Status')

        if not authority or payment_status != 'OK':
            return _frontend_redirect('UnSuccessfulPayPage', reason='cancelled')

        payment = Payment.objects.select_related('questionnaire').filter(
            authority=authority,
        ).first()
        if payment is None:
            return _frontend_redirect('UnSuccessfulPayPage', reason='payment_not_found')

        if payment.successful:
            return _frontend_redirect(
                'SuccessfulPayPage',
                questionnaire_id=payment.questionnaire_id,
            )

        try:
            gateway = verify_gateway_payment(amount=payment.price, authority=authority)
        except PaymentGatewayError:
            return _frontend_redirect('UnSuccessfulPayPage', reason='verification_failed')

        if gateway.code not in (100, 101):
            return _frontend_redirect('UnSuccessfulPayPage', reason='verification_rejected')

        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related('questionnaire').get(pk=payment.pk)
            payment.successful = True
            payment.save(update_fields=['successful'])
            Questionnaire.objects.filter(pk=payment.questionnaire_id).update(is_paid=True)

        return _frontend_redirect(
            'SuccessfulPayPage',
            questionnaire_id=payment.questionnaire_id,
        )


class PaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = Payment.objects.filter(user=request.user).select_related('user').order_by('-created_at')
        return Response(PaymentSerializer(payments, many=True).data)
