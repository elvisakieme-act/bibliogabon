from django.contrib import admin

from document_processing.models import DocumentPage, ExtractedText, SearchIndexRecord


def test_document_processing_models_are_registered_in_admin():
    assert DocumentPage in admin.site._registry
    assert ExtractedText in admin.site._registry
    assert SearchIndexRecord in admin.site._registry
