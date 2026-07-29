from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.v1.errors import error_response
from api.v1.serializers import (
    CurrentUserUpdateSerializer,
    ErrorResponseSerializer,
    LogoutSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    TokenRefreshRequestSerializer,
    TokenRequestSerializer,
    UserSerializer,
    serialize_user,
)


def email_exists_response() -> Response:
    return error_response(
        code="email_exists",
        message="A user with this email already exists.",
        status_code=status.HTTP_409_CONFLICT,
        field_errors={"email": ["A user with this email already exists."]},
    )


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=["Authentication"],
        summary="Register an individual learner account",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(RegisterResponseSerializer, description="User created with JWT tokens"),
            400: OpenApiResponse(ErrorResponseSerializer, description="Invalid registration data"),
            409: OpenApiResponse(ErrorResponseSerializer, description="Email already exists"),
            415: OpenApiResponse(ErrorResponseSerializer, description="Request body must use application/json"),
        },
        examples=[
            OpenApiExample(
                "Registration request",
                value={
                    "email": "reader@example.ga",
                    "password": "StrongPass123!",
                    "display_name": "Reader One",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Successful registration",
                value={
                    "user": {
                        "id": 1,
                        "email": "reader@example.ga",
                        "display_name": "Reader One",
                        "account_type": "individual",
                    },
                    "tokens": {"access": "<jwt>", "refresh": "<jwt>"},
                },
                response_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            email_errors = serializer.errors.get("email", [])
            if any(getattr(error, "code", "") == "email_exists" for error in email_errors):
                return email_exists_response()
            return error_response(
                code="invalid_registration",
                message="Registration data is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors=serializer.errors,
            )
        try:
            user = get_user_model().objects.create_user(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                display_name=serializer.validated_data.get("display_name", ""),
                account_type=get_user_model().AccountType.INDIVIDUAL,
            )
        except IntegrityError:
            return email_exists_response()
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

    @extend_schema(
        tags=["Authentication"],
        summary="Log out the current user",
        request=LogoutSerializer,
        responses={
            204: None,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Logout request",
                value={"refresh": "<jwt>"},
                request_only=True,
            )
        ],
    )
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
            refresh = RefreshToken(refresh_token)
        except TokenError:
            return error_response(
                code="invalid_refresh_token",
                message="The refresh token is invalid.",
                status_code=status.HTTP_400_BAD_REQUEST,
                field_errors={"refresh": ["Invalid refresh token."]},
            )
        if str(refresh["user_id"]) != str(request.user.pk):
            return error_response(
                code="refresh_token_user_mismatch",
                message="The refresh token does not belong to the authenticated user.",
                status_code=status.HTTP_403_FORBIDDEN,
                field_errors={"refresh": ["Refresh token belongs to a different user."]},
            )
        refresh.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Current user"],
        summary="Retrieve the current user",
        responses={200: UserSerializer, 401: ErrorResponseSerializer},
        examples=[
            OpenApiExample(
                "Current user",
                value={
                    "id": 1,
                    "email": "reader@example.ga",
                    "display_name": "Reader One",
                    "account_type": "individual",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        return Response(serialize_user(request.user), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Current user"],
        summary="Update the current user",
        request=CurrentUserUpdateSerializer,
        responses={
            200: UserSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Current user update",
                value={"display_name": "Updated Reader"},
                request_only=True,
            ),
            OpenApiExample(
                "Updated current user",
                value={
                    "id": 1,
                    "email": "reader@example.ga",
                    "display_name": "Updated Reader",
                    "account_type": "individual",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def patch(self, request):
        serializer = CurrentUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = request.user
        for field in ["display_name", "phone_number"]:
            if field in serializer.validated_data:
                setattr(user, field, serializer.validated_data[field])
        user.save(update_fields=["display_name", "phone_number", "updated_at"])
        return Response(serialize_user(user), status=status.HTTP_200_OK)


class DocumentedTokenObtainPairView(TokenObtainPairView):
    @extend_schema(
        tags=["Authentication"],
        summary="Obtain JWT tokens",
        request=TokenRequestSerializer,
        responses={
            200: TokenPairSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "JWT login",
                value={
                    "email": "reader@example.ga",
                    "password": "StrongPass123!",
                },
                request_only=True,
            ),
            OpenApiExample(
                "JWT token pair",
                value={"access": "<jwt>", "refresh": "<jwt>"},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DocumentedTokenRefreshView(TokenRefreshView):
    @extend_schema(
        tags=["Authentication"],
        summary="Refresh a JWT access token",
        request=TokenRefreshRequestSerializer,
        responses={
            200: TokenPairSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            415: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "JWT refresh",
                value={"refresh": "<jwt>"},
                request_only=True,
            ),
            OpenApiExample(
                "Refreshed JWT token pair",
                value={"access": "<jwt>", "refresh": "<jwt>"},
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
