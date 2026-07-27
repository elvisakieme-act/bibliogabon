from django.contrib import admin

from document_ingestion.models import DocumentAsset, DocumentVersion, ProcessingJob


def test_document_ingestion_models_are_registered_in_admin():
    assert DocumentVersion in admin.site._registry
    assert DocumentAsset in admin.site._registry
    assert ProcessingJob in admin.site._registry
