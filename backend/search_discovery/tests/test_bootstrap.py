from django.apps import apps


def test_search_discovery_app_is_installed():
    assert apps.is_installed("search_discovery")
