from django.apps import apps


def test_catalog_app_is_installed():
    assert apps.is_installed("catalog")
