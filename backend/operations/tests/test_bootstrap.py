from django.apps import apps


def test_operations_app_is_installed():
    assert apps.is_installed("operations")
