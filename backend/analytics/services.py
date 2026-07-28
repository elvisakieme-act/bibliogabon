from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Organization, OrganizationMembership
from analytics.models import AnalyticsRun, DailyUsageAggregate
from document_reader.models import PageAccessLog, ReaderSession


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
