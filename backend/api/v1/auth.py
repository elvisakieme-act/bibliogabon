from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.v1.errors import error_response
from api.v1.serializers import CurrentUserUpdateSerializer, RegisterSerializer, serialize_user


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            email_errors = serializer.errors.get("email", [])
            if any(getattr(error, "code", "") == "email_exists" for error in email_errors):
                return error_response(
                    code="email_exists",
                    message="A user with this email already exists.",
                    status_code=status.HTTP_409_CONFLICT,
                    field_errors={"email": serializer.errors["email"]},
                )
            return error_response(
                code="invalid_registration",
                message="Registration data is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors=serializer.errors,
            )
        user = get_user_model().objects.create_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            display_name=serializer.validated_data.get("display_name", ""),
            account_type=get_user_model().AccountType.INDIVIDUAL,
        )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": serialize_user(user),
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = str(request.data.get("refresh", "")).strip()
        if not refresh_token:
            return error_response(
                code="refresh_token_required",
                message="A refresh token is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"refresh": ["This field is required."]},
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            return error_response(
                code="invalid_refresh_token",
                message="The refresh token is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"refresh": ["Invalid refresh token."]},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serialize_user(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = CurrentUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = request.user
        for field in ["display_name", "phone_number"]:
            if field in serializer.validated_data:
                setattr(user, field, serializer.validated_data[field])
        user.save(update_fields=["display_name", "phone_number", "updated_at"])
        return Response(serialize_user(user), status=status.HTTP_200_OK)
