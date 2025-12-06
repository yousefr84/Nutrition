from rest_framework import serializers

from payments.models import Discount as Discount
from payments.models import Payment as Payment
from payments.models import Price as Price
from users.serializers import UserSerializer as UserSerializer


class PaymentSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Payment
        fields = '__all__'


class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Price
        fields = ["price"]


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ['percent', 'usage']


# class PeymentSerializer(serializers.ModelSerializer):
#     questionnaire = QuestionnaireDeatailSerializer()
#
#     class Meta:
#         models = Payment
#         fields = '__all__'
