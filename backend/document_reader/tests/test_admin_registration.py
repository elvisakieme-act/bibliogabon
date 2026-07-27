from django.contrib import admin

from document_reader.models import PageAccessLog, ReaderSession


def test_document_reader_models_are_registered_in_admin():
    assert ReaderSession in admin.site._registry
    assert PageAccessLog in admin.site._registry
