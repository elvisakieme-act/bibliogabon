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


def _create_organization_offer(slug):
    return CommercialOffer.objects.create(
        name=f"Offer {slug}",
        slug=slug,
        offer_type=CommercialOffer.OfferType.ORGANIZATION,
        billing_period=CommercialOffer.BillingPeriod.ANNUAL,
        price_xaf=100000,
        duration_days=365,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
    )


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
def test_generate_institution_report_counts_failed_organization_payments():
    period_start = timezone.datetime(2026, 1, 1).date()
    period_end = timezone.datetime(2026, 1, 31).date()
    paid_at = timezone.make_aware(timezone.datetime(2026, 1, 12, 10, 0, 0))
    failed_at = timezone.make_aware(timezone.datetime(2026, 1, 13, 11, 0, 0))
    organization = create_organization(slug="payment-report-org")
    other_organization = create_organization(slug="other-payment-report-org")
    user = create_user(email="individual-payment@example.ga")
    offer = _create_organization_offer("payment-report-offer")

    PaymentTransaction.objects.create(
        organization=organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MANUAL_INVOICE,
        status=PaymentTransaction.Status.SUCCEEDED,
        amount_xaf=100000,
        idempotency_key="payment-report-succeeded",
        succeeded_at=paid_at,
    )
    PaymentTransaction.objects.create(
        organization=organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        status=PaymentTransaction.Status.FAILED,
        amount_xaf=25000,
        idempotency_key="payment-report-failed",
        failed_at=failed_at,
    )
    PaymentTransaction.objects.create(
        organization=other_organization,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        status=PaymentTransaction.Status.FAILED,
        amount_xaf=30000,
        idempotency_key="payment-report-other-org-failed",
        failed_at=failed_at,
    )
    PaymentTransaction.objects.create(
        user=user,
        offer=offer,
        provider=PaymentTransaction.Provider.MOBILE_MONEY,
        status=PaymentTransaction.Status.FAILED,
        amount_xaf=35000,
        idempotency_key="payment-report-user-failed",
        failed_at=failed_at,
    )

    report = generate_institution_report(organization, period_start, period_end)

    assert report.metrics["commercial"]["payments"] == {
        "succeeded_count": 1,
        "succeeded_amount_xaf": 100000,
        "failed_count": 1,
        "failed_amount_xaf": 25000,
    }


@pytest.mark.django_db
def test_generate_institution_report_counts_members_active_at_period_end():
    period_start = timezone.datetime(2026, 1, 1).date()
    period_end = timezone.datetime(2026, 1, 31).date()
    starts_at = timezone.make_aware(timezone.datetime(2025, 12, 20, 9, 0, 0))
    ended_at = timezone.make_aware(timezone.datetime(2026, 1, 15, 17, 0, 0))
    active_through_period_end = timezone.make_aware(timezone.datetime(2026, 2, 1, 0, 0, 0))
    organization = create_organization(slug="period-end-member-org")
    ended_mid_period = create_user(email="ended-mid-period@example.ga")
    active_at_period_end = create_user(email="active-at-period-end@example.ga")

    create_active_membership(
        ended_mid_period,
        organization,
        starts_at=starts_at,
        ends_at=ended_at,
    )
    create_active_membership(
        active_at_period_end,
        organization,
        starts_at=starts_at,
        ends_at=active_through_period_end,
    )

    report = generate_institution_report(organization, period_start, period_end)

    assert report.metrics["access"]["active_member_count"] == 1


@pytest.mark.django_db
def test_generate_institution_report_counts_entitlement_lifecycle_buckets():
    period_start = timezone.datetime(2026, 1, 1).date()
    period_end = timezone.datetime(2026, 1, 31).date()
    starts_at = timezone.make_aware(timezone.datetime(2025, 12, 20, 9, 0, 0))
    organization = create_organization(slug="entitlement-bucket-org")
    other_organization = create_organization(slug="other-entitlement-bucket-org")
    user = create_user(email="individual-entitlement@example.ga")

    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
    )
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
        ends_at=timezone.make_aware(timezone.datetime(2026, 1, 12, 10, 0, 0)),
    )
    Entitlement.objects.create(
        organization=organization,
        source=Entitlement.Source.ADMIN_GRANT,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
        revoked_at=timezone.make_aware(timezone.datetime(2026, 1, 16, 11, 0, 0)),
    )
    Entitlement.objects.create(
        organization=other_organization,
        source=Entitlement.Source.ORGANIZATION_QUOTA,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
    )
    Entitlement.objects.create(
        user=user,
        source=Entitlement.Source.INDIVIDUAL_SUBSCRIPTION,
        access_right=Entitlement.AccessRight.READ,
        scope_type=Entitlement.ScopeType.GLOBAL,
        starts_at=starts_at,
        revoked_at=timezone.make_aware(timezone.datetime(2026, 1, 18, 11, 0, 0)),
    )

    report = generate_institution_report(organization, period_start, period_end)

    assert report.metrics["access"]["entitlements"] == {
        "active": 2,
        "expired": 1,
        "revoked": 1,
    }


@pytest.mark.django_db
def test_generate_institution_report_keeps_same_title_documents_separate():
    at = timezone.make_aware(timezone.datetime(2026, 1, 5, 9, 0, 0))
    organization = create_organization(slug="same-title-report-org")
    user = create_user(email="same-title-reader@example.ga")
    create_active_membership(user, organization, starts_at=at - timezone.timedelta(days=1))
    first_document = create_document(slug="shared-title-one", access_model="subscription")
    second_document = create_document(slug="shared-title-two", access_model="subscription")
    second_document.title = first_document.title
    second_document.academic_domain = first_document.academic_domain
    second_document.save(update_fields=["title", "academic_domain", "updated_at"])
    create_reader_activity(user=user, document=first_document, started_at=at, page_views=1)
    create_reader_activity(user=user, document=second_document, started_at=at + timezone.timedelta(hours=1), page_views=1)

    report = generate_institution_report(organization, at.date(), at.date())

    by_document = report.metrics["usage"]["by_document"]
    assert len(by_document) == 2
    assert {row["document_slug"] for row in by_document} == {first_document.slug, second_document.slug}


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
