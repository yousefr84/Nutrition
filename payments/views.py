# Create your views here.
import json

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from payments.models import Discount as Discount
from payments.models import Payment as PaymentHistory
from payments.models import Price as Price
from payments.serializers import DiscountSerializer as DiscountSerializer
from payments.serializers import PaymentSerializer as PaymentSerializer
from payments.serializers import PriceSerializer as PriceSerializer
from users.models import CustomUser


# Create your views here.

class PayCheckAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payment = Price.objects.get(id=1)
        price = PriceSerializer(payment).data['price']
        return Response({"price": price})

    def post(self, request):
        input = request.data['discount_code']
        payment = Price.objects.get(id=1)
        amount = int(PriceSerializer(payment).data['price'])
        try:
            discount_code = Discount.objects.get(code=input)
            data = DiscountSerializer(discount_code).data
            if data['usage'] == 0:
                return Response(data={"error": "The discount code has expired."}, status=status.HTTP_400_BAD_REQUEST)
            discount = data['percent']
            amount = amount - (discount / 100) * amount
            discount_code.usage -= 1
            discount_code.save()
            return Response({'price': amount}, status=status.HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response(data={'error': "discount code is wrong"}, status=status.HTTP_404_NOT_FOUND)


class PaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    sandbox = 'www'
    MERCHANT =  '25cbacf6-c1eb-41ff-8d01-53bf686044f2' # باید تو settings.py تعریف شده باشه
    ZP_API_REQUEST = f"https://{sandbox}.zarinpal.com/pg/rest/WebGate/PaymentRequest.json"
    ZP_API_VERIFY = f"https://{sandbox}.zarinpal.com/pg/rest/WebGate/PaymentVerification.json"
    ZP_API_STARTPAY = f"https://{sandbox}.zarinpal.com/pg/StartPay/"
    CallbackURL = 'https://api.innonet.ir/payments/payment/verify/'  # اصلاح شده برای مطابقت با URL

    def post(self, request):
        amount = int(request.data['price'])  # فرض می‌کنیم فیلد price تو سریالایزر وجود داره
        description = request.data['description']
        username = request.data['username']
        print(amount)
        description = description
        phone = '09120478082'
        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return Response({'status': False, 'code': 'invalid_user'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            "MerchantID": self.MERCHANT,
            "Amount": amount,
            "Description": description,
            "Phone": phone,
            "CallbackURL": self.CallbackURL,
        }

        data = json.dumps(data)
        headers = {'content-type': 'application/json', 'content-length': str(len(data))}

        try:
            response = requests.post(self.ZP_API_REQUEST, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                response_data = response.json()
                payment = PaymentHistory.objects.create(
                    price=amount,
                    user=user,
                    description=description,
                    authority=response_data['Authority']
                )

                payment.save()
                if response_data['Status'] == 100:
                    return Response({
                        'status': True,
                        'url': self.ZP_API_STARTPAY + str(response_data['Authority']),
                        'authority': response_data['Authority']
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({'status': False, 'code': str(response_data['Status'])},
                                    status=status.HTTP_400_BAD_REQUEST)
            return Response({'status': False, 'code': str(response.status_code)}, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.Timeout:
            return Response({'status': False, 'code': 'timeout'}, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.ConnectionError:
            return Response({'status': False, 'code': 'connection error'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    def get(self, request):
        authority = request.GET.get('Authority')
        status_param = request.GET.get('Status')

        if not authority or status_param != 'OK':
            return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')

        try:
            try:
                payment = PaymentHistory.objects.get(authority=authority)
            except PaymentHistory.DoesNotExist:
                return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')
            amount = payment.price
        except KeyError:
            return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')

        data = {
            "MerchantID": self.MERCHANT,
            "Amount": amount,
            "Authority": authority,
        }
        data = json.dumps(data)
        headers = {'content-type': 'application/json', 'content-length': str(len(data))}

        try:
            response = requests.post(self.ZP_API_VERIFY, data=data, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                if response_data['Status'] == 100:
                    payment.successful = True
                    payment.save()
                    return HttpResponseRedirect('https://innonet.ir/main/SuccessfulPayPage')
                else:
                    return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')
            return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')
        except requests.exceptions.RequestException:
            return HttpResponseRedirect('https://innonet.ir/main/UnSuccessfulPayPage')


class PaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        username = request.query_params.get('username')
        payments = PaymentHistory.objects.filter(user__username=username).order_by('-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
