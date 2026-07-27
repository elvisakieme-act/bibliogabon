import pytest
from django.db import IntegrityError

from catalog.models import AcademicDomain


@pytest.mark.django_db
def test_academic_domain_supports_parent_hierarchy():
    parent = AcademicDomain.objects.create(name="Sciences", slug="sciences")
    child = AcademicDomain.objects.create(
        name="Informatique",
        slug="informatique",
        parent=parent,
    )

    assert str(child) == "Sciences / Informatique"
    assert child.parent == parent


@pytest.mark.django_db
def test_academic_domain_slug_is_unique():
    AcademicDomain.objects.create(name="Droit", slug="droit")

    with pytest.raises(IntegrityError):
        AcademicDomain.objects.create(name="Droit public", slug="droit")
