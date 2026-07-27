from django.contrib import admin

from search_discovery.models import DocumentSearchIndex


def test_search_discovery_models_are_registered_in_admin():
    assert DocumentSearchIndex in admin.site._registry


def test_search_discovery_admin_keeps_internal_text_read_only():
    model_admin = admin.site._registry[DocumentSearchIndex]

    readonly_fields = model_admin.get_readonly_fields(request=None)

    assert "page_text" in readonly_fields
    assert "metadata_text" in readonly_fields
