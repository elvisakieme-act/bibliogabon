from django.apps import apps


def test_document_reader_app_is_installed():
    assert apps.is_installed("document_reader")
