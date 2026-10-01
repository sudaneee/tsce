"""
Admissions calendar and fee rules (from the TSCE flyer):

  • Early Bird 15%  — payment before the cohort's early-bird deadline (automatic)
  • Excellence 50%  — WAEC from 2020 to date with 5 A's or more (staff verifies)
  • Scholarship ≤40% — intake exam / interview performance (staff assigns)

Discounts do NOT stack: the single highest approved discount applies.
All percentages and thresholds come from SiteSettings, so staff can change them.
"""
from dataclasses import dataclass
from datetime import date

from django.db.models import Count
from django.utils import timezone

from apps.core.models import SiteSettings

from .models import Application, DiscountType


def long_date(d: date) -> str:
    return f"{d.day} {d:%B %Y}"  # "1 October 2026" (%-d isn't portable to Windows)


def today() -> date:
    """Today in Lagos (TIME_ZONE) — deadlines are local calendar dates."""
    return timezone.localdate()


@dataclass(frozen=True)
class AdmissionsState:
    open: bool
    message: str = ""


def admissions_state(settings: SiteSettings, on: date | None = None) -> AdmissionsState:
    on = on or today()
    cohort = settings.current_cohort
    if not settings.accepting_applications or cohort is None:
        return AdmissionsState(False, "Applications are currently closed. Please check back for the next cohort.")
    if cohort.enrolment_opens and on < cohort.enrolment_opens:
        return AdmissionsState(False, f"Applications for the {cohort.name} open on {long_date(cohort.enrolment_opens)}.")
    if cohort.enrolment_closes and on > cohort.enrolment_closes:
        return AdmissionsState(False, f"Applications for the {cohort.name} closed on {long_date(cohort.enrolment_closes)}.")
    return AdmissionsState(True)


def early_bird_open(cohort, on: date | None = None) -> bool:
    deadline = cohort.early_bird_deadline if cohort else None
    return bool(deadline and (on or today()) < deadline)


def excellence_eligible(settings: SiteSettings, waec_status, waec_year, num_as) -> bool:
    return (
        waec_status == Application.WaecStatus.AVAILABLE
        and (waec_year or 0) >= settings.excellence_min_waec_year
        and (num_as or 0) >= settings.excellence_min_as
    )


@dataclass(frozen=True)
class Quote:
    fee: int
    discount_type: str
    discount_pct: int
    discount_amount: int
    amount_payable: int


def quote(programme, cohort, settings: SiteSettings, on: date | None = None) -> Quote:
    """Amount payable now. Only the automatic (early-bird) discount applies at checkout."""
    pct = settings.early_bird_pct if early_bird_open(cohort, on) else 0
    discount = round(programme.fee * pct / 100)
    return Quote(
        fee=programme.fee,
        discount_type=DiscountType.EARLY_BIRD if pct else "",
        discount_pct=pct,
        discount_amount=discount,
        amount_payable=programme.fee - discount,
    )


def seats_taken(cohort) -> dict[int, int]:
    """Paid, non-rejected applications per programme id for a cohort."""
    if cohort is None:
        return {}
    rows = (
        Application.objects.filter(cohort=cohort, payment_status=Application.PaymentStatus.PAID)
        .exclude(status=Application.Status.REJECTED)
        .values("programme_id")
        .annotate(n=Count("id"))
    )
    return {r["programme_id"]: r["n"] for r in rows}
