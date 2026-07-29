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


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    account_type = serializers.CharField(read_only=True)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class TokenRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class RegisterResponseSerializer(serializers.Serializer):
    user = UserSerializer(read_only=True)
    tokens = TokenPairSerializer(read_only=True)


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    field_errors = serializers.DictField(read_only=True)


class ErrorResponseSerializer(serializers.Serializer):
    error = ErrorDetailSerializer(read_only=True)


class ReaderSessionCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)


class ReaderSessionSerializer(serializers.Serializer):
    session_key = serializers.UUIDField(read_only=True)
    document_id = serializers.IntegerField(read_only=True)
    version_id = serializers.IntegerField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class ReaderPageSerializer(serializers.Serializer):
    session_key = serializers.UUIDField(read_only=True)
    document_id = serializers.IntegerField(read_only=True)
    version_id = serializers.IntegerField(read_only=True)
    page_number = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True)
    language_code = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)
