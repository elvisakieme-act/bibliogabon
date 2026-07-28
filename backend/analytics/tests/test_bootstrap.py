from django.apps import apps


def test_analytics_app_is_installed():
    assert apps.is_installed("analytics")
