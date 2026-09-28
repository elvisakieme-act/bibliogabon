from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
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


def _membership_windows(user_ids) -> dict[int, list[tuple]]:
    """Charge en une seule requete les fenetres d'adhesion des utilisateurs
    concernes. L'attribution interrogeait la base par activite : deux
    requetes chacune, soit 100 000 requetes pour une journee a 50 000 pages
    lues, et trente fois cela pour un rapport mensuel."""
    windows: dict[int, list[tuple]] = defaultdict(list)
    rows = OrganizationMembership.objects.filter(
        user_id__in=[user_id for user_id in user_ids if user_id is not None],
        status=OrganizationMembership.Status.ACTIVE,
        organization__status=Organization.Status.ACTIVE,
    ).values_list("user_id", "organization_id", "starts_at", "ends_at")
    for user_id, organization_id, starts_at, ends_at in rows:
        windows[user_id].append((organization_id, starts_at, ends_at))
    return windows


def _single_organization_id_at(windows, user_id, at):
    """Une activite n'est attribuee que si son auteur appartenait a une
    seule organisation a cet instant precis. L'instant compte : une
    adhesion qui commence ou se termine en cours de journee ne vaut pas
    pour le reste de la journee."""
    organization_ids = {
        organization_id
        for organization_id, starts_at, ends_at in windows.get(user_id, ())
        if starts_at <= at and (ends_at is None or ends_at > at)
    }
    if len(organization_ids) != 1:
        return None
    return next(iter(organization_ids))


# Les quatre dimensions d'un agregat, plus l'instant qui decide de
# l'attribution. Lues en tuples : instancier les modeles ne servirait a rien.
_ACTIVITY_DIMENSIONS = (
    "user_id",
    "document_id",
    "document__academic_domain_id",
    "document__access_model",
)


def _count_activity(rows, windows, counters, counter_name):
    for user_id, document_id, domain_id, access_model, at in rows:
        organization_id = _single_organization_id_at(windows, user_id, at)
        if organization_id is None:
            continue
        counters[(organization_id, document_id, domain_id, access_model)][counter_name] += 1


def _distinct_page_views(start, end):
    """Une page lue compte une fois, quel que soit le nombre de requêtes.

    Le journal enregistre **toute** remise de contenu : c'est une garantie
    d'audit, et elle ne doit pas dépendre de la représentation demandée. Mais
    le lecteur demande désormais le texte *et* l'image d'une même page, ce qui
    produirait deux lignes pour une seule lecture et doublerait, en silence,
    tous les rapports institutionnels.

    Le dédoublonnage porte sur (session, page) : dans une même session de
    lecture, la page 7 lue est la page 7 lue. Cela corrige au passage un défaut
    antérieur — un lecteur qui revenait en arrière gonflait le compte de son
    institution.

    La première ligne est conservée, donc l'horodatage retenu est celui du
    premier accès : c'est lui qui situe la lecture dans la fenêtre
    d'appartenance à l'organisation.
    """
    seen = set()
    rows = []
    for row in (
        PageAccessLog.objects.filter(accessed_at__gte=start, accessed_at__lt=end)
        .order_by("accessed_at", "pk")
        .values_list("session_id", "page_number", *_ACTIVITY_DIMENSIONS, "accessed_at")
    ):
        key = (row[0], row[1])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row[2:])
    return rows


def _activity_counters(start, end):
    """Compte les sessions et les pages lues d'une journee, par dimension.
    N'ecrit rien : la lecture est separee de la persistance."""
    sessions = list(
        ReaderSession.objects.filter(started_at__gte=start, started_at__lt=end).values_list(
            *_ACTIVITY_DIMENSIONS, "started_at"
        )
    )
    page_logs = _distinct_page_views(start, end)
    windows = _membership_windows({row[0] for row in sessions} | {row[0] for row in page_logs})
    counters = defaultdict(lambda: {"reader_session_count": 0, "page_view_count": 0})
    _count_activity(sessions, windows, counters, "reader_session_count")
    _count_activity(page_logs, windows, counters, "page_view_count")
    return counters


def _persist_daily_aggregates(day, counters) -> list[DailyUsageAggregate]:
    """Remplace l'etat du jour. Les lignes dont la dimension a disparu sont
    supprimees : une activite devenue ambigue ne doit pas laisser derriere
    elle une attribution que le recalcul ne produit plus."""
    aggregates = []
    with transaction.atomic():
        current_keys = set(counters)
        stale_ids = [
            existing.pk
            for existing in DailyUsageAggregate.objects.filter(date=day).only(
                "pk", "organization_id", "document_id", "academic_domain_id", "access_model"
            )
            if (
                existing.organization_id,
                existing.document_id,
                existing.academic_domain_id,
                existing.access_model,
            )
            not in current_keys
        ]
        if stale_ids:
            DailyUsageAggregate.objects.filter(pk__in=stale_ids).delete()

        for (
            organization_id,
            document_id,
            domain_id,
            access_model,
        ), values in counters.items():
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
    return aggregates


@contextmanager
def _analytics_run(run):
    """Un run enregistre son propre sort. Sans ce passage oblige, une
    exception laisserait la ligne en RUNNING indefiniment, et rien ne
    distinguerait un calcul en cours d'un calcul mort."""
    try:
        yield run
    except Exception as exc:
        run.status = AnalyticsRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)
        run.save(update_fields=["status", "finished_at", "error_message"])
        raise
    run.status = AnalyticsRun.Status.SUCCEEDED
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at", "metadata"])


def build_daily_usage_aggregate(day) -> list[DailyUsageAggregate]:
    start, end = _day_bounds(day)
    run = AnalyticsRun.objects.create(
        run_type=AnalyticsRun.RunType.DAILY_USAGE_AGGREGATE,
        period_start=day,
        period_end=day,
        metadata={"date": day.isoformat()},
    )
    with _analytics_run(run):
        return _persist_daily_aggregates(day, _activity_counters(start, end))


def _period_bounds(period_start, period_end):
    start = timezone.make_aware(datetime.combine(period_start, time.min))
    end = timezone.make_aware(
        datetime.combine(period_end + timezone.timedelta(days=1), time.min)
    )
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
        .values(
            "document_id",
            "document__title",
            "document__slug",
            "academic_domain__name",
            "access_model",
        )
        .annotate(
            reader_session_count=Sum("reader_session_count"),
            page_view_count=Sum("page_view_count"),
            active_day_count=Count("date", distinct=True),
        )
        .order_by("-reader_session_count", "-page_view_count", "document__title", "document_id")
    )
    return [
        {
            "document_id": row["document_id"],
            "document_title": row["document__title"],
            "document_slug": row["document__slug"],
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


def _access_metrics(organization, start, end):
    """Qui avait le droit d'acceder, et combien de sieges etaient ouverts.
    Ne compte que des agregats : aucun identifiant de lecteur ne sort d'ici."""
    overlapping = Q(starts_at__lt=end) & (Q(ends_at__isnull=True) | Q(ends_at__gt=start))
    # Une adhesion « active » se mesure a la fin de la periode, pas sur un
    # chevauchement : un rapport annonce un effectif, pas un cumul de passages.
    active_at_period_end = Q(starts_at__lt=end) & (
        Q(ends_at__isnull=True) | Q(ends_at__gte=end)
    )
    active_quotas = OrganizationQuota.objects.filter(
        organization=organization,
        status=OrganizationQuota.Status.ACTIVE,
    ).filter(overlapping)
    return {
        "active_member_count": OrganizationMembership.objects.filter(
            organization=organization,
            status=OrganizationMembership.Status.ACTIVE,
        )
        .filter(active_at_period_end)
        .count(),
        "entitlements": {
            # « actif » et « expire » se recouvrent volontairement : un droit
            # qui s'est eteint en cours de periode a bien ete actif pendant.
            "active": Entitlement.objects.filter(
                organization=organization,
                starts_at__lt=end,
                revoked_at__isnull=True,
            )
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=start))
            .count(),
            "expired": Entitlement.objects.filter(
                organization=organization,
                revoked_at__isnull=True,
                ends_at__gte=start,
                ends_at__lt=end,
            ).count(),
            "revoked": Entitlement.objects.filter(
                organization=organization,
                revoked_at__gte=start,
                revoked_at__lt=end,
            ).count(),
        },
        "quotas": {
            "active_count": active_quotas.count(),
            "seat_limit_total": _sum_amount(active_quotas, "seat_limit"),
        },
        "subscriptions": {
            "active_count": Subscription.objects.filter(
                organization=organization,
                status=Subscription.Status.ACTIVE,
            )
            .filter(overlapping)
            .count(),
        },
    }


def _commercial_metrics(organization, start, end):
    """Ce qui a ete encaisse et ce qui a echoue, sur la periode. Un paiement
    compte a la date de son sort, pas a celle de sa creation."""
    succeeded = PaymentTransaction.objects.filter(
        organization=organization,
        status=PaymentTransaction.Status.SUCCEEDED,
        succeeded_at__gte=start,
        succeeded_at__lt=end,
    )
    failed = PaymentTransaction.objects.filter(
        organization=organization,
        status=PaymentTransaction.Status.FAILED,
        failed_at__gte=start,
        failed_at__lt=end,
    )
    return {
        "payments": {
            "succeeded_count": succeeded.count(),
            "succeeded_amount_xaf": _sum_amount(succeeded, "amount_xaf"),
            "failed_count": failed.count(),
            "failed_amount_xaf": _sum_amount(failed, "amount_xaf"),
        },
    }


def _support_metrics(organization, start, end):
    tickets = SupportTicket.objects.filter(organization=organization)
    return {
        "opened_count": tickets.filter(opened_at__gte=start, opened_at__lt=end).count(),
        "resolved_count": tickets.filter(resolved_at__gte=start, resolved_at__lt=end).count(),
    }


def _usage_metrics(organization, period_start, period_end):
    """La lecture, uniquement par agregats deja anonymises : le rapport part
    de DailyUsageAggregate et jamais de PageAccessLog, qui nomme le lecteur."""
    aggregates = DailyUsageAggregate.objects.filter(
        organization=organization,
        date__gte=period_start,
        date__lte=period_end,
    ).select_related("document", "academic_domain")
    totals = aggregates.aggregate(
        reader_session_count=Sum("reader_session_count"),
        page_view_count=Sum("page_view_count"),
        distinct_document_count=Count("document_id", distinct=True),
    )
    return {
        "reader_session_count": totals["reader_session_count"] or 0,
        "page_view_count": totals["page_view_count"] or 0,
        "distinct_document_count": totals["distinct_document_count"] or 0,
        "by_day": _usage_by_day(aggregates),
        "by_domain": _usage_by_domain(aggregates),
        "by_document": _usage_by_document(aggregates),
        "by_access_model": _usage_by_access_model(aggregates),
    }


def _build_institution_metrics(organization, period_start, period_end):
    start, end = _period_bounds(period_start, period_end)
    return {
        "access": _access_metrics(organization, start, end),
        "commercial": _commercial_metrics(organization, start, end),
        "support": _support_metrics(organization, start, end),
        "usage": _usage_metrics(organization, period_start, period_end),
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
    with _analytics_run(run):
        current_day = period_start
        while current_day <= period_end:
            build_daily_usage_aggregate(current_day)
            current_day = current_day + timezone.timedelta(days=1)

        report, _ = InstitutionReport.objects.update_or_create(
            organization=organization,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "status": InstitutionReport.Status.GENERATED,
                "metrics": _build_institution_metrics(organization, period_start, period_end),
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
        run.metadata = {"organization_id": organization.pk, "report_id": report.pk}
        return report


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
