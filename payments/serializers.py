from rest_framework import serializers

from payments.models import Payment
from users.serializers import UserSerializer


class DiscountCodeSerializer(serializers.Serializer):
    discount_code = serializers.CharField(max_length=10, trim_whitespace=True)


class PaymentRequestSerializer(serializers.Serializer):
    questionnaire_id = serializers.IntegerField(min_value=1)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
    )
    discount_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=10,
        trim_whitespace=True,
    )


class PaymentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id',
            'pid',
            'price',
            'questionnaire',
            'date',
            'created_at',
            'successful',
            'user',
            'description',
        )
        read_only_fields = fields
