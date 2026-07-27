from django.contrib import admin

from search_discovery.models import DocumentSearchIndex


def test_search_discovery_models_are_registered_in_admin():
    assert DocumentSearchIndex in admin.site._registry
