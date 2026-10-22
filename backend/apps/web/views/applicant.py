"""My applications, the invoice / checkout, payment status and the receipt."""
import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.admissions.models import Application
from apps.admissions.services import sync_programme_quote
from apps.core.exceptions import ServiceError
from apps.core.models import SiteSettings
from apps.payments import services as payments
from apps.payments.gateways import GatewayError
from apps.payments.models import Payment
from apps.payments.views import SESSION_REF, callback_url

from .. import presenters
from ..forms import PayForm
from ..throttle import allow
from .common import applicant_required, error_code, error_text

logger = logging.getLogger(__name__)
MAX_AUTO_CHECKS = 10


def _mine(request):
    return (Application.objects.filter(user=request.user)
            .select_related("programme", "cohort", "award_request", "enrollment__student"))


@applicant_required
def my_applications(request):
    apps = list(_mine(request).order_by("-created_at"))
    cards = [{"app": a, "tracker": presenters.tracker(a), "next": presenters.next_step(a)} for a in apps]
    return render(request, "web/applicant/my_applications.html", {
        "cards": cards, "parent": request.user.role == "parent", "charge": presenters.payer_charge(),
        "unknown_payment": request.GET.get("payment") == "unknown",
    })


@applicant_required
def pay(request, number):
    app = get_object_or_404(_mine(request), number=number)
    settings = SiteSettings.load()
    if app.status == Application.Status.ADMITTED and app.amount_paid == 0:
        # Show what will really be charged today (the early bird depends on the payment date).
        sync_programme_quote(app, settings)
    opts = presenters.pay_options(app)
    plan = request.POST.get("plan") or request.GET.get("plan") or "full"
    plan = "half" if plan == "half" and opts.half else "full"
    ctx = {"app": app, "opts": opts, "plan": plan, "parent": request.user.role == "parent",
           "app_fee": presenters.application_fee_due(app), "settings": settings,
           "environment": _environment(), "failed": request.GET.get("failed"), "error": "", "notice": ""}

    if app.status == Application.Status.REJECTED or app.payment_status == Application.PaymentStatus.PAID \
            or app.status == Application.Status.AWAITING_VERIFICATION \
            or (app.status != Application.Status.ADMITTED and not opts.is_balance):
        return render(request, "web/applicant/pay_blocked.html", ctx)

    if request.method == "POST":
        form = PayForm(request.POST)
        if not allow(request, "payment"):
            ctx["error"] = "Too many payment attempts. Please wait a minute and try again."
        elif not form.is_valid():
            ctx["error"] = "Please choose how you'd like to pay."
        elif form.shown(plan) != opts.due(plan):
            ctx["notice"] = (f"The amount has changed to ₦{opts.due(plan):,} (for example, the early-bird period has "
                             "ended). Please check it and press Pay again.")
        else:
            try:
                payment = payments.start_checkout(app, Payment.Purpose.PROGRAMME_FEE, callback_url(request), plan)
            except ServiceError as exc:
                if error_code(exc) == "already_paid":
                    return redirect("web:pay", number=app.number)
                ctx["error"] = error_text(exc)
            else:
                request.session[SESSION_REF] = payment.reference
                return redirect(payment.checkout_url)
    return render(request, "web/applicant/pay.html", ctx)


def _environment():
    from django.conf import settings as dj

    return "simulated" if dj.PAYMENT_GATEWAY == "simulator" else dj.ZAINPAY["ENVIRONMENT"]


def _payment_for(request, ref) -> Payment:
    qs = Payment.objects.select_related("application__programme", "application__cohort", "application__enrollment__student")
    if not request.user.is_portal_staff:
        qs = qs.filter(Q(user=request.user) | Q(application__user=request.user))
    return get_object_or_404(qs, reference=ref, kind=Payment.Kind.CHARGE)


@applicant_required
def payment_status(request, ref):
    """Where the payer lands after Zainpay: confirmed, still confirming, or failed."""
    payment = _payment_for(request, ref)
    checks = _int(request.GET.get("check"))
    if payment.status == Payment.Status.PENDING and checks:
        try:
            payment = payments.process_payment(payment)
        except GatewayError as exc:
            logger.warning("Status check for %s failed: %s", ref, exc)
    app = payment.application
    if payment.status == Payment.Status.FAILED and app:
        return redirect(f"{reverse('web:pay', kwargs={'number': app.number})}?failed={payment.reference}")
    if payment.status == Payment.Status.PENDING:
        nxt = checks + 1 if checks < MAX_AUTO_CHECKS else None
        return render(request, "web/applicant/payment_pending.html", {"payment": payment, "app": app, "next_check": nxt})
    app.refresh_from_db()
    return render(request, "web/applicant/payment_done.html", {
        "payment": payment, "app": app, "paid_for": presenters.paid_for(payment),
        "parent": request.user.role == "parent", "opts": presenters.pay_options(app),
        "student_no": getattr(getattr(app, "enrollment", None), "student", None) and app.enrollment.student.student_no,
        "fresh": request.GET.get("fresh") != "0",
    })


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


@applicant_required
def payment_check(request, ref):
    """"Check now" button on the confirming page."""
    if request.method != "POST":
        return redirect("web:payment", ref=ref)
    payment = _payment_for(request, ref)
    if allow(request, "payment"):
        try:
            payment = payments.process_payment(payment)
        except GatewayError:
            messages.warning(request, "We couldn't reach the payment provider. Please try again shortly.")
    if payment.status == Payment.Status.PENDING:
        messages.info(request, "Zainpay hasn't confirmed this payment yet. If you paid, you don't need to pay again.")
    return redirect("web:payment", ref=ref)


@applicant_required
def receipt(request, ref):
    payment = _payment_for(request, ref)
    if payment.status not in (Payment.Status.SUCCESS, Payment.Status.REFUNDED):
        raise Http404
    return render(request, "web/applicant/receipt.html", {
        "payment": payment, "app": payment.application, "lines": presenters.receipt_lines(payment),
        "paid_for": presenters.paid_for(payment), "environment": _environment(), "charge": presenters.payer_charge(),
        "student_no": payment.application and getattr(getattr(payment.application, "enrollment", None), "student", None)
                      and payment.application.enrollment.student.student_no,
    })


# ---------------------------------------------------------------------------
# Old page addresses (emails already sent, bookmarks, Zainpay returns)
# ---------------------------------------------------------------------------
def legacy(request, page):
    q = request.GET
    if page == "login":
        target = "/account/login/" + (f"?{q.urlencode()}" if q else "")
    elif page == "register":
        target = "/account/register/"
    elif page == "verify-email":
        target = "/account/verify-email/" + (f"?{q.urlencode()}" if q else "")
    elif page == "application":
        target = "/apply/" + (f"?programme={q['programme']}" if q.get("programme") else "")
    elif page == "payment" and q.get("app"):
        target = reverse("web:pay", kwargs={"number": q["app"]})
    elif page == "success" and q.get("ref"):
        target = reverse("web:payment", kwargs={"ref": q["ref"]})
    else:
        target = "/my-applications/"
    return redirect(target, permanent=False)


def legacy_staff(request, page):
    q = request.GET
    if page == "applications" and q.get("id"):
        return redirect(reverse("web:staff-application", kwargs={"number": q["id"]}))
    if page == "payments" and q.get("ref"):
        return redirect(reverse("web:staff-payment", kwargs={"ref": q["ref"]}))
    target = {"dashboard": "web:staff-dashboard", "applications": "web:staff-applications", "scholarships": "web:staff-awards",
              "payments": "web:staff-payments", "staff": "web:staff-team", "settings": "web:staff-settings"
              }.get(page, "web:staff-dashboard")  # the old "coming soon" pages → the dashboard
    keep = {k: q[k] for k in ("status",) if q.get(k)}
    return redirect(reverse(target) + (f"?{urlencode(keep)}" if keep else ""))


def legacy_student(request):
    """The old JS student pages → the student portal."""
    return redirect("/student/")
