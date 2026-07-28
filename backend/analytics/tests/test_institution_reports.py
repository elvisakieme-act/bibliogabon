import pytest
from django.utils import timezone

from accounts.models import Entitlement
from analytics.models import InstitutionReport
from analytics.services import generate_institution_report, serialize_institution_report
from analytics.tests.factories import (
    create_active_membership,
    create_document,
    create_organization,
    create_reader_activity,
    create_user,
)
from billing.models import CommercialOffer, OrganizationQuota, PaymentTransaction, Subscription
from operations.models import AuditLog, SupportTicket


def _forbidden_keys(payload):
    forbidden = {"email", "user_id", "user_ids", "session_key", "client_ip", "user_agent", "page_number"}
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in forbidden:
                    found.add(key)
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


@pytest.mark.django_db
def test_generate_institution_report_builds_private_organization_metrics():
    start = timezone.make_aware(timezone.datetime(2026, 1, 1, 9, 0, 0))
    end_date = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="report-org")
    user = create_user(email="report-reader@example.ga")
    create_active_membership(user, organization, starts_at=start - timezone.timedelta(days=1))
    document = create_document(slug="report-doc", access_model="subscription")
    create_reader_activity(user=user, document=document, started_at=start, page_views=3)
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=start - timezone.timedelta(days=1),
    )
    offer = CommercialOffer.objects.create(
        name="Institution annual",
        slug="institution-annual",
        offer_type=CommercialOffer.OfferType.ORGANIZATION,
        billing_period=CommercialOffer.BillingPeriod.ANNUAL,
        price_xaf=100000,
        duration_days=365,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )
    Subscription.objects.create(
        offer=offer,
        organization=organization,
        status=Subscription.Status.ACTIVE,
        starts_at=start - timezone.timedelta(days=1),
        ends_at=start + timezone.timedelta(days=365),
    )
    OrganizationQuota.objects.create(
        organization=organization,
        offer=offer,
        status=OrganizationQuota.Status.ACTIVE,
        seat_limit=50,
        starts_at=start - timezone.timedelta(days=1),
        ends_at=start + timezone.timedelta(days=365),
    )
    PaymentTransaction.objects.create(
        organization=organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MANUAL_INVOICE,
        status=PaymentTransaction.Status.SUCCEEDED,
        amount_xaf=100000,
        idempotency_key="report-payment",
        succeeded_at=start,
    )
    SupportTicket.objects.create(
        title="Acces institution",
        description="Verification du contrat",
        organization=organization,
        opened_at=start,
    )

    report = generate_institution_report(organization, start.date(), end_date, generated_by=user)

    assert report.organization == organization
    assert report.period_start == start.date()
    assert report.period_end == end_date
    assert report.metrics["access"]["active_member_count"] == 1
    assert report.metrics["access"]["entitlements"]["active"] == 1
    assert report.metrics["access"]["quotas"]["active_count"] == 1
    assert report.metrics["access"]["quotas"]["seat_limit_total"] == 50
    assert report.metrics["access"]["subscriptions"]["active_count"] == 1
    assert report.metrics["commercial"]["payments"]["succeeded_amount_xaf"] == 100000
    assert report.metrics["support"]["opened_count"] == 1
    assert report.metrics["usage"]["reader_session_count"] == 1
    assert report.metrics["usage"]["page_view_count"] == 3
    assert report.metrics["usage"]["by_document"][0]["document_title"] == document.title
    assert AuditLog.objects.filter(event_type="institution_report_generated", target_id=str(report.pk)).exists()


@pytest.mark.django_db
def test_generate_institution_report_is_idempotent_for_same_period():
    start = timezone.datetime(2026, 1, 1).date()
    end = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="idempotent-report-org")

    first = generate_institution_report(organization, start, end)
    second = generate_institution_report(organization, start, end)

    assert first.pk == second.pk
    assert InstitutionReport.objects.count() == 1


@pytest.mark.django_db
def test_serialized_institution_report_excludes_personal_reader_data():
    start = timezone.datetime(2026, 1, 1).date()
    end = timezone.datetime(2026, 1, 31).date()
    organization = create_organization(slug="private-report-org")
    report = generate_institution_report(organization, start, end)

    payload = serialize_institution_report(report)

    assert _forbidden_keys(payload) == set()
