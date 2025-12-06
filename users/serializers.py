from rest_framework import serializers

from users.models import CustomUser


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Invalid phone number")
        return value


from rest_framework import serializers
from users.models import CustomUser


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField()

    def validate_phone(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Invalid phone number")
        return value

    def validate_code(self, value):
        if not value.isdigit() or len(value) not in (4, 5, 6):
            raise serializers.ValidationError("Invalid code format")
        return value


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "phone", "first_name", "last_name")
        read_only_fields = ("id", "phone", "first_name", "last_name")


class CompleteProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name")
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
        }



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "phone", "first_name", "last_name"]
