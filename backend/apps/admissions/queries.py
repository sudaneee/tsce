"""Staff-side queries over applications: filters, dashboard numbers, sidebar badges."""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.academics.models import Enrollment
from apps.core.models import SiteSettings
from apps.payments.models import Payment

from .models import Application, AwardRequest


def filter_applications(p):
    """Staff application filters (?status=&programme=&award=&q=&from=&to=) → (queryset, counts by status)."""
    qs = Application.objects.select_related("programme", "cohort", "user", "award_request")
    if p.get("programme"):
        qs = qs.filter(programme__slug=p["programme"])
    if p.get("award"):
        qs = qs.filter(award_request__isnull=False) if p["award"] == "any" else qs.filter(award_request__status=p["award"])
    if p.get("from"):
        qs = qs.filter(created_at__date__gte=p["from"])
    if p.get("to"):
        qs = qs.filter(created_at__date__lte=p["to"])
    if p.get("q"):
        q = p["q"].strip()
        qs = qs.filter(Q(number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                       | Q(email__icontains=q) | Q(phone__icontains=q) | Q(user__email__icontains=q)
                       | Q(user__full_name__icontains=q))
    counts = dict(qs.values_list("status").annotate(n=Count("id")))
    counts["all"] = sum(counts.values())
    if p.get("status"):
        qs = qs.filter(status=p["status"])
    return qs.order_by("-created_at"), counts


def staff_summary() -> dict:
    """Numbers for the staff dashboard and the sidebar badges."""
    settings = SiteSettings.load()
    cohort = settings.current_cohort
    apps = Application.objects.filter(cohort=cohort) if cohort else Application.objects.none()
    by_status = dict(apps.values_list("status").annotate(n=Count("id")))
    charges = Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.SUCCESS)
    week_ago = timezone.now() - timedelta(days=7)
    revenue = lambda qs: qs.aggregate(t=Sum("amount"))["t"] or 0  # noqa: E731
    return {
        "intake": cohort.name if cohort else None,
        "cohortStart": cohort.start_date if cohort else None,
        "applications": {"total": sum(by_status.values()), **by_status},
        "awardsToVerify": AwardRequest.objects.filter(status=AwardRequest.Status.PENDING,
                                                      application__status=Application.Status.AWAITING_VERIFICATION).count(),
        "enrolled": Enrollment.objects.filter(cohort=cohort).count() if cohort else 0,
        "revenue": {
            "total": revenue(charges),
            "applicationFees": revenue(charges.filter(purpose=Payment.Purpose.APPLICATION_FEE)),
            "programmeFees": revenue(charges.filter(purpose=Payment.Purpose.PROGRAMME_FEE)),
            "lastWeek": revenue(charges.filter(verified_at__gte=week_ago)),
        },
        "paymentsPending": Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.PENDING,
                                                  created_at__gte=week_ago).count(),
        "duplicates": len(_duplicate_refs()),
        "seats": [
            {"programme": r["programme__name"], "taken": r["n"], "capacity": r["programme__capacity"]}
            for r in Enrollment.objects.filter(cohort=cohort)
            .values("programme__name", "programme__capacity").annotate(n=Count("id")).order_by("-n")
        ] if cohort else [],
    }


def sidebar_counts() -> dict:
    """The two badges in the staff sidebar (cheaper than the full summary)."""
    return {"awards": AwardRequest.objects.filter(status=AwardRequest.Status.PENDING,
                                                  application__status=Application.Status.AWAITING_VERIFICATION).count(),
            "duplicates": len(_duplicate_refs())}


def _duplicate_refs():
    from apps.payments.services import counted_charge_ids

    counted = counted_charge_ids()
    return list(Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.SUCCESS,
                                       application__isnull=False).exclude(id__in=counted)
                .values_list("reference", flat=True))
