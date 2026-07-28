from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import Entitlement, Organization, OrganizationMembership
from analytics.models import AnalyticsRun, DailyUsageAggregate, InstitutionReport
from billing.models import OrganizationQuota, PaymentTransaction, Subscription
from document_reader.models import PageAccessLog, ReaderSession
from operations.models import SupportTicket
from operations.services import record_audit_event


def _day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    return start, start + timezone.timedelta(days=1)


def _single_active_organization_for_user_at(user, at):
    organization_ids = list(
        OrganizationMembership.objects.filter(
            user=user,
            status=OrganizationMembership.Status.ACTIVE,
            starts_at__lte=at,
            organization__status=Organization.Status.ACTIVE,
        )
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
        .values_list("organization_id", flat=True)
        .distinct()
    )
    if len(organization_ids) != 1:
        return None
    return Organization.objects.get(pk=organization_ids[0])


def _dimension_for_activity(*, user, document, at):
    organization = _single_active_organization_for_user_at(user, at)
    if organization is None:
        return None
    return (
        organization.pk,
        document.pk,
        document.academic_domain_id,
        document.access_model,
    )


def build_daily_usage_aggregate(day) -> list[DailyUsageAggregate]:
    start, end = _day_bounds(day)
    run = AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.DAILY_USAGE_AGGREGATE,
        period_start=day,
        period_end=day,
        metadata={"date": day.isoformat()},
    )
    counters = defaultdict(lambda: {"reader_session_count": 0, "page_view_count": 0})

    try:
        sessions = ReaderSession.objects.filter(started_at__gte=start, started_at__lt=end).select_related(
            "user",
            "document",
            "document__academic_domain",
        )
        for session in sessions:
            key = _dimension_for_activity(user=session.user, document=session.document, at=session.started_at)
            if key is not None:
                counters[key]["reader_session_count"] += 1

        page_logs = PageAccessLog.objects.filter(accessed_at__gte=start, accessed_at__lt=end).select_related(
            "user",
            "document",
            "document__academic_domain",
        )
        for log in page_logs:
            key = _dimension_for_activity(user=log.user, document=log.document, at=log.accessed_at)
            if key is not None:
                counters[key]["page_view_count"] += 1

        aggregates = []
        with transaction.atomic():
            current_keys = set(counters.keys())
            existing_aggregates = DailyUsageAggregate.objects.filter(date=day).only(
                "pk",
                "organization_id",
                "document_id",
                "academic_domain_id",
                "access_model",
            )
            for existing in existing_aggregates:
                existing_key = (
                    existing.organization_id,
                    existing.document_id,
                    existing.academic_domain_id,
                    existing.access_model,
                )
                if existing_key not in current_keys:
                    existing.delete()

            for (organization_id, document_id, domain_id, access_model), values in counters.items():
                aggregate, _ = DailyUsageAggregate.objects.update_or_create(
                    date=day,
                    organization_id=organization_id,
                    document_id=document_id,
                    academic_domain_id=domain_id,
                    access_model=access_model,
                    defaults={
                        "reader_session_count": values["reader_session_count"],
                        "page_view_count": values["page_view_count"],
                        "distinct_document_count": 1,
                    },
                )
                aggregates.append(aggregate)

        run.status = AnalyticsRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        return aggregates
    except Exception as exc:
        run.status = AnalyticsRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])
        raise


def _period_bounds(period_start, period_end):
    start = timezone.make_aware(datetime.combine(period_start, time.min))
    end = timezone.make_aware(datetime.combine(period_end + timezone.timedelta(days=1), time.min))
    return start, end


def _sum_amount(queryset, field_name):
    return queryset.aggregate(total=Sum(field_name))["total"] or 0


def _usage_by_day(aggregates):
    rows = (
        aggregates.values("date")
        .annotate(
            reader_session_count=Sum("reader_session_count"),
            page_view_count=Sum("page_view_count"),
            distinct_document_count=Sum("distinct_document_count"),
        )
        .order_by("date")
    )
    return [
        {
            "date": row["date"].isoformat(),
            "reader_session_count": row["reader_session_count"] or 0,
            "page_view_count": row["page_view_count"] or 0,
            "distinct_document_count": row["distinct_document_count"] or 0,
        }
        for row in rows
    ]


def _usage_by_domain(aggregates):
    rows = (
        aggregates.values("academic_domain__name")
        .annotate(
            reader_session_count=Sum("reader_session_count"),
            page_view_count=Sum("page_view_count"),
            distinct_document_count=Count("document_id", distinct=True),
        )
        .order_by("academic_domain__name")
    )
    return [
        {
            "domain_name": row["academic_domain__name"],
            "reader_session_count": row["reader_session_count"] or 0,
            "page_view_count": row["page_view_count"] or 0,
            "distinct_document_count": row["distinct_document_count"] or 0,
        }
        for row in rows
    ]


def _usage_by_document(aggregates):
    rows = (
        aggregates.filter(document_id__isnull=False)
        .values("document__title", "academic_domain__name", "access_model")
        .annotate(
            reader_session_count=Sum("reader_session_count"),
            page_view_count=Sum("page_view_count"),
            active_day_count=Count("date", distinct=True),
        )
        .order_by("-reader_session_count", "-page_view_count", "document__title")
    )
    return [
        {
            "document_title": row["document__title"],
            "domain_name": row["academic_domain__name"],
            "access_model": row["access_model"],
            "reader_session_count": row["reader_session_count"] or 0,
            "page_view_count": row["page_view_count"] or 0,
            "active_day_count": row["active_day_count"] or 0,
        }
        for row in rows
    ]


def _usage_by_access_model(aggregates):
    rows = (
        aggregates.values("access_model")
        .annotate(
            reader_session_count=Sum("reader_session_count"),
            page_view_count=Sum("page_view_count"),
            distinct_document_count=Count("document_id", distinct=True),
        )
        .order_by("access_model")
    )
    return [
        {
            "access_model": row["access_model"],
            "reader_session_count": row["reader_session_count"] or 0,
            "page_view_count": row["page_view_count"] or 0,
            "distinct_document_count": row["distinct_document_count"] or 0,
        }
        for row in rows
    ]


def _build_institution_metrics(organization, period_start, period_end):
    start, end = _period_bounds(period_start, period_end)
    overlapping = Q(starts_at__lt=end) & (Q(ends_at__isnull=True) | Q(ends_at__gt=start))
    usage_aggregates = DailyUsageAggregate.objects.filter(
        organization=organization,
        date__gte=period_start,
        date__lte=period_end,
    ).select_related("document", "academic_domain")
    usage_totals = usage_aggregates.aggregate(
        reader_session_count=Sum("reader_session_count"),
        page_view_count=Sum("page_view_count"),
        distinct_document_count=Count("document_id", distinct=True),
    )
    active_memberships = OrganizationMembership.objects.filter(
        organization=organization,
        status=OrganizationMembership.Status.ACTIVE,
    ).filter(overlapping)
    active_entitlements = Entitlement.objects.filter(
        organization=organization,
        starts_at__lt=end,
        revoked_at__isnull=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=start))
    active_subscriptions = Subscription.objects.filter(
        organization=organization,
        status=Subscription.Status.ACTIVE,
    ).filter(overlapping)
    active_quotas = OrganizationQuota.objects.filter(
        organization=organization,
        status=OrganizationQuota.Status.ACTIVE,
    ).filter(overlapping)
    succeeded_payments = PaymentTransaction.objects.filter(
        organization=organization,
        status=PaymentTransaction.Status.SUCCEEDED,
        succeeded_at__gte=start,
        succeeded_at__lt=end,
    )
    support_tickets = SupportTicket.objects.filter(organization=organization)

    return {
        "access": {
            "active_member_count": active_memberships.count(),
            "entitlements": {
                "active": active_entitlements.count(),
            },
            "quotas": {
                "active_count": active_quotas.count(),
                "seat_limit_total": _sum_amount(active_quotas, "seat_limit"),
            },
            "subscriptions": {
                "active_count": active_subscriptions.count(),
            },
        },
        "commercial": {
            "payments": {
                "succeeded_count": succeeded_payments.count(),
                "succeeded_amount_xaf": _sum_amount(succeeded_payments, "amount_xaf"),
            },
        },
        "support": {
            "opened_count": support_tickets.filter(opened_at__gte=start, opened_at__lt=end).count(),
            "resolved_count": support_tickets.filter(resolved_at__gte=start, resolved_at__lt=end).count(),
        },
        "usage": {
            "reader_session_count": usage_totals["reader_session_count"] or 0,
            "page_view_count": usage_totals["page_view_count"] or 0,
            "distinct_document_count": usage_totals["distinct_document_count"] or 0,
            "by_day": _usage_by_day(usage_aggregates),
            "by_domain": _usage_by_domain(usage_aggregates),
            "by_document": _usage_by_document(usage_aggregates),
            "by_access_model": _usage_by_access_model(usage_aggregates),
        },
    }


def generate_institution_report(organization, period_start, period_end, generated_by=None):
    if period_start > period_end:
        raise ValueError("period_start must be on or before period_end")
    run = AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.INSTITUTION_REPORT,
        organization=organization,
        period_start=period_start,
        period_end=period_end,
        metadata={"organization_id": organization.pk},
    )
    try:
        current_day = period_start
        while current_day <= period_end:
            build_daily_usage_aggregate(current_day)
            current_day = current_day + timezone.timedelta(days=1)

        metrics = _build_institution_metrics(organization, period_start, period_end)
        report, _ = InstitutionReport.objects.update_or_create(
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "status": InstitutionReport.Status.GENERATED,
                "metrics": metrics,
                "generated_by": generated_by,
                "generated_at": timezone.now(),
            },
        )
        record_audit_event(
            actor=generated_by,
            event_type="institution_report_generated",
            target=report,
            summary=f"Institution report generated for {organization.name}",
            metadata={
                "organization_id": organization.pk,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "report_id": report.pk,
            },
        )
        run.status = AnalyticsRun.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.metadata = {"organization_id": organization.pk, "report_id": report.pk}
        run.save(update_fields=["status", "finished_at", "metadata"])
        return report
    except Exception as exc:
        run.status = AnalyticsRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])
        raise


def serialize_institution_report(report):
    return {
        "id": report.pk,
        "organization": {
            "id": report.organization_id,
            "name": report.organization.name,
            "slug": report.organization.slug,
        },
        "period": {
            "start": report.period_start.isoformat(),
            "end": report.period_end.isoformat(),
        },
        "status": report.status,
        "metrics": report.metrics,
        "generated_at": report.generated_at.isoformat(),
    }
