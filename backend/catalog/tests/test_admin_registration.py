from django.contrib import admin

from catalog.models import AcademicDomain, Author, Document, DocumentAuthor, RightsAgreement


def test_catalog_models_are_registered_in_admin():
    assert AcademicDomain in admin.site._registry
    assert Author in admin.site._registry
    assert Document in admin.site._registry
    assert DocumentAuthor in admin.site._registry
    assert RightsAgreement in admin.site._registry
