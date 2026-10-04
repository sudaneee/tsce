"""
Admissions calendar and fee rules.

ONE payment (decided 4 Oct 2026): the PROGRAMME FEE, with the application fee
(SiteSettings.application_fee, ₦5,000) added to it. Applicants who paid the
application fee separately under the earlier two-step flow are credited.
Discounts apply to the programme (tuition) part only — never the application fee:

  • Early Bird 15%  — programme fee paid before the cohort's early-bird deadline (automatic)
  • Excellence 50%  — WAEC/NECO from 2020 to date with 5 A's or more, verified in person by staff

Discounts do NOT stack: the single highest applies. (The flyer's Performance
Scholarship was discontinued on 1 Oct 2026.) Percentages and thresholds come
from SiteSettings, so staff can change them.
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
    fee: int                  # programme (tuition) fee before discount
    discount_type: str
    discount_pct: int
    discount_amount: int
    amount_payable: int       # tuition − discount + application fee (if not already paid)
    application_fee: int = 0  # the application-fee part of amount_payable


def quote(programme, cohort, settings: SiteSettings, on: date | None = None, award_pct: int = 0) -> Quote:
    """
    Programme fee payable if paid on `on` (default today): the higher of an
    approved Excellence Award (award_pct) and the early bird, never both.
    """
    eb_pct = settings.early_bird_pct if early_bird_open(cohort, on) else 0
    if award_pct and award_pct >= eb_pct:
        kind, pct = DiscountType.EXCELLENCE, award_pct
    elif eb_pct:
        kind, pct = DiscountType.EARLY_BIRD, eb_pct
    else:
        kind, pct = "", 0
    discount = round(programme.fee * pct / 100)
    return Quote(fee=programme.fee, discount_type=kind, discount_pct=pct, discount_amount=discount,
                 amount_payable=programme.fee - discount)


def programme_quote(app, settings: SiteSettings, on: date | None = None) -> Quote:
    """
    What this application pays: tuition (with its award or the early bird) plus
    the application fee — unless that was already paid separately (credited).
    """
    from .models import AwardRequest

    award = getattr(app, "award_request", None)
    approved = award is not None and award.status == AwardRequest.Status.APPROVED
    award_pct = (award.awarded_pct or 0) if approved else 0
    q = quote(app.programme, app.cohort, settings, on, award_pct=award_pct)
    app_fee = 0 if getattr(app, "application_fee_paid_at", None) else (app.application_fee or 0)
    return Quote(fee=q.fee, discount_type=q.discount_type, discount_pct=q.discount_pct,
                 discount_amount=q.discount_amount, amount_payable=q.amount_payable + app_fee, application_fee=app_fee)


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
