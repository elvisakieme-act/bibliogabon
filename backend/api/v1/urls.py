from django.urls import path

from api.v1.auth import (
    CurrentUserView,
    DocumentedTokenObtainPairView,
    DocumentedTokenRefreshView,
    LogoutView,
    RegisterView,
)
from api.v1.views import api_index

app_name = "api-v1"

urlpatterns = [
    path("", api_index, name="index"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", DocumentedTokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh/", DocumentedTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
