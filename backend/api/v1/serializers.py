from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers


def serialize_user(user) -> dict:
    return {
        "id": user.pk,
        "email": user.email,
        "display_name": user.display_name,
        "account_type": user.account_type,
    }


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)

    def validate_email(self, value):
        email = get_user_model().objects.normalize_email(value)
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists.",
                code="email_exists",
            )
        return email


class CurrentUserUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
