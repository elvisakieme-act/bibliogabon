from django.conf import settings
from django.contrib.auth import get_user_model


def test_project_uses_custom_user_model():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert get_user_model().__name__ == "User"
