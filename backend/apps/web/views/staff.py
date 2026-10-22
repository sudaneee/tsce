"""
The staff portal as server-rendered pages: dashboard, applications (+ award
decisions, reminders, rejections), Excellence Awards, payments (+ Zainpay
check, refunds), staff accounts, settings, notifications and search.
Every action calls the same services as before.
"""
import csv
import logging
import mimetypes
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Student
from apps.accounts import services as accounts
from apps.accounts.models import StaffProfile, User
from apps.accounts.views import temporary_password
from apps.admissions.models import Application, AwardRequest
from apps.admissions.services import reject_application, review_award, send_reminder
from apps.admissions.staff_views import filter_applications, sidebar_counts, staff_summary
from apps.comms.models import Notification
from apps.core.exceptions import ServiceError
from apps.core.models import SiteSettings
from apps.payments import services as payments
from apps.payments.gateways import GatewayError
from apps.payments.models import Payment
from apps.payments.views import filter_payments, is_duplicate_row, payments_summary
from apps.programmes.models import Cohort, Programme

from .. import presenters
from ..forms import (AdmissionsForm, DiscountsForm, InstitutionForm, IntakeForm, NoteForm, NotificationSettingsForm,
                     RefundForm, StaffMemberForm)
from .common import LOGIN_URL, error_text

logger = logging.getLogger(__name__)
PAGE_SIZE = 25
STATUSES = ["Pending", "Awaiting Verification", "Admitted", "Enrolled", "Rejected"]


# ---------------------------------------------------------------------------
# Access + shell
# ---------------------------------------------------------------------------
def staff_required(view=None, *, admin=False):
    def decorate(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{LOGIN_URL}?{urlencode({'role': 'staff', 'next': request.get_full_path()})}")
            if not user.is_portal_staff:
                return redirect("/my-applications/")
            if user.must_change_password:
                return redirect(f"/account/password/?{urlencode({'next': request.get_full_path()})}")
            if admin and user.role != User.Role.ADMIN:
                raise PermissionDenied
            return fn(request, *args, **kwargs)
        return wrapper
    return decorate(view) if view else decorate


def shell(request, active, title, subtitle, **ctx):
    """Context every staff page needs: sidebar badges, the bell, who is signed in."""
    mine = Notification.objects.filter(recipient=request.user)
    from apps.comms.models import SupportTicket

    counts = {**sidebar_counts(), "tickets": SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count()}
    return {"active": active, "page_title": title, "page_sub": subtitle, "counts": counts,
            "bell": list(mine[:8]), "unread": mine.filter(read=False).count(),
            "is_admin": request.user.role == User.Role.ADMIN, **ctx}


def paginate(request, qs):
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def csv_response(filename, header, rows):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("﻿")  # Excel opens UTF-8 (₦, names) correctly with a BOM
    w = csv.writer(resp)
    w.writerow(header)
    w.writerows(rows)
    return resp


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@staff_required
def dashboard(request):
    s = staff_summary()
    hour = timezone.localtime().hour
    recent = Application.objects.select_related("programme", "user").order_by("-created_at")[:6]
    seats = [{**r, "pct": round(r["taken"] / r["capacity"] * 100) if r["capacity"] else 0} for r in s["seats"]]
    return render(request, "web/staff/dashboard.html", shell(
        request, "dashboard", "Dashboard", "Institution overview", s=s, recent=recent, seats=seats,
        greeting="Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening",
        first_name=" ".join(request.user.full_name.split()[:2])))


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
@staff_required
def applications(request):
    qs, counts = filter_applications(request.GET)
    if request.GET.get("export") == "csv":
        return csv_response("tsce-applications.csv",
                            ["Application", "Applicant", "Phone", "Email", "Account", "Account type", "Programme", "Intake", "Applied",
                             "Application fee", "Award", "Status", "Programme fee", "Fee status", "Amount paid", "Balance", "Balance due"],
                            [[a.number, a.full_name, a.phone, a.email, a.user.email, "parent" if a.user.role == "parent" else "self",
                              a.programme.name, a.cohort.name, timezone.localtime(a.created_at).date().isoformat(),
                              "Paid separately" if a.application_fee_paid_at else "Included in programme fee",
                              getattr(getattr(a, "award_request", None), "status", ""), a.status, a.amount_payable,
                              a.payment_status, a.amount_paid, a.balance, a.balance_due_date or ""] for a in qs[:5000]])
    page, query = paginate(request, qs)
    chips = [("", "All", counts.get("all", 0))] + [(s, s, counts.get(s, 0)) for s in STATUSES]
    return render(request, "web/staff/applications.html", shell(
        request, "applications", "Applications", "Admissions pipeline", page=page, query=query, chips=chips,
        f=request.GET, programmes=Programme.objects.order_by("name")))


def _application(number):
    return get_object_or_404(
        Application.objects.select_related("programme", "cohort", "user", "award_request", "enrollment__student")
        .prefetch_related("events", "payments"), number=number)


@staff_required
def application_detail(request, number):
    app = _application(number)
    note_form = NoteForm(request.POST or None)
    if request.method == "POST" and note_form.is_valid():
        action, note = request.POST.get("action"), note_form.cleaned_data["note"]
        try:
            if action in ("award-yes", "award-no"):
                app = review_award(app, action == "award-yes", request.user, note)
                messages.success(request, f"Excellence Award {'approved' if action == 'award-yes' else 'declined'} — "
                                          f"{app.full_name} admitted, programme fee ₦{app.amount_payable:,}.")
            elif action == "remind":
                what = send_reminder(app, request.user)
                messages.success(request, f"{app.user.full_name} was reminded about the {what} (portal + email).")
            elif action == "reject":
                reject_application(app, request.user, note)
                messages.warning(request, f"Application {app.number} rejected.")
            else:
                messages.error(request, "Unknown action.")
        except ServiceError as exc:
            messages.error(request, error_text(exc))
        return redirect("web:staff-application", number=app.number)

    award = getattr(app, "award_request", None)
    return render(request, "web/staff/application.html", shell(
        request, "applications", "Applications", "Admissions pipeline", app=app, award=award,
        tracker=presenters.tracker(app), app_fee=presenters.application_fee_due(app),
        payments=app.payments.order_by("-created_at"), events=app.events.order_by("-at", "-id"),
        can_award=app.status == Application.Status.AWAITING_VERIFICATION and award and award.status == AwardRequest.Status.PENDING,
        can_remind=app.status == Application.Status.ADMITTED or app.payment_status == Application.PaymentStatus.PART_PAID,
        can_reject=app.status not in (Application.Status.ENROLLED, Application.Status.REJECTED),
        student=getattr(getattr(app, "enrollment", None), "student", None)))


@staff_required
def waec_file(request, number):
    app = get_object_or_404(Application, number=number)
    if not app.waec_file:
        raise Http404
    ctype = mimetypes.guess_type(app.waec_file.name)[0] or "application/octet-stream"
    ext = app.waec_file.name.rsplit(".", 1)[-1]
    resp = FileResponse(app.waec_file.open("rb"), content_type=ctype)
    resp["Content-Disposition"] = f'inline; filename="WAEC-{app.number.replace("/", "-")}.{ext}"'
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


# ---------------------------------------------------------------------------
# Excellence Awards
# ---------------------------------------------------------------------------
@staff_required
def awards(request):
    tab = request.GET.get("tab") or "Pending"
    qs = (Application.objects.filter(award_request__isnull=False)
          .select_related("programme", "user", "award_request").order_by("-created_at"))
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                       | Q(user__full_name__icontains=q) | Q(user__email__icontains=q))
    tabs = [(t, "To verify" if t == "Pending" else t,
             qs.count() if t == "All" else qs.filter(award_request__status=t).count())
            for t in ("Pending", "Approved", "Rejected", "All")]
    rows = list(qs if tab == "All" else qs.filter(award_request__status=tab))
    if tab == "Pending":  # people waiting for a decision first
        rows.sort(key=lambda a: a.status != Application.Status.AWAITING_VERIFICATION)
    s = SiteSettings.load()
    return render(request, "web/staff/awards.html", shell(
        request, "awards", "Excellence Awards", "Verify results in person", rows=rows, tabs=tabs, tab=tab, q=q, s=s))


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
PURPOSE = {"application_fee": "Application fee", "programme_fee": "Programme fee"}


@staff_required
def payments_list(request):
    counted = payments.counted_charge_ids()
    qs = filter_payments(request.GET)
    rows = list(qs[:2000])
    for p in rows:
        p.is_dup = is_duplicate_row(p, counted)
    if request.GET.get("dup"):
        rows = [p for p in rows if p.is_dup]
    if request.GET.get("export") == "csv":
        return csv_response("tsce-payments.csv",
                            ["Reference", "Kind", "For", "Installment", "Applicant", "Account", "Application", "Amount", "Status",
                             "Duplicate", "Created", "Confirmed"],
                            [[p.reference, p.kind, PURPOSE.get(p.purpose, ""), p.get_installment_display(), p.name, p.email,
                              p.application.number if p.application_id else "", (-1 if p.kind == "refund" else 1) * p.amount,
                              p.status, "yes" if p.is_dup else "", timezone.localtime(p.created_at).strftime("%Y-%m-%d %H:%M"),
                              timezone.localtime(p.verified_at).strftime("%Y-%m-%d %H:%M") if p.verified_at else ""] for p in rows])
    page, query = paginate(request, rows)
    return render(request, "web/staff/payments.html", shell(
        request, "payments", "Payments", "Zainpay transactions", page=page, query=query, f=request.GET,
        summary=payments_summary(counted)))


@staff_required
def payment_detail(request, ref):
    p = get_object_or_404(Payment.objects.select_related("application", "parent"), reference=ref)
    refund_form = RefundForm(request.POST if request.POST.get("action") == "refund" else None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "check" and p.kind == Payment.Kind.CHARGE:
            try:
                p = payments.process_payment(p)
                messages.info(request, f"Checked with Zainpay — status: {p.status}.")
            except GatewayError:
                messages.error(request, "We couldn't reach Zainpay. Please try again shortly.")
            return redirect("web:staff-payment", ref=ref)
        if action == "refund" and refund_form.is_valid():
            try:
                payments.refund_duplicate(p, request.user, refund_form.cleaned_data["transferRef"], refund_form.cleaned_data["note"])
                messages.success(request, f"Refund of ₦{p.amount:,} to {p.name} recorded.")
                return redirect("web:staff-payment", ref=ref)
            except ServiceError as exc:
                messages.error(request, error_text(exc))
    student = getattr(getattr(p.application, "enrollment", None), "student", None) if p.application_id else None
    return render(request, "web/staff/payment.html", shell(
        request, "payments", "Payments", "Zainpay transactions", p=p, purpose=PURPOSE.get(p.purpose, "—"),
        is_dup=payments.is_duplicate(p), refund_form=refund_form, student=student))


@staff_required
def staff_receipt(request, ref):
    p = get_object_or_404(Payment.objects.select_related("application__enrollment__student"), reference=ref,
                          kind=Payment.Kind.CHARGE, status__in=[Payment.Status.SUCCESS, Payment.Status.REFUNDED])
    from .applicant import _environment

    enrollment = getattr(p.application, "enrollment", None) if p.application_id else None
    return render(request, "web/applicant/receipt.html", {
        "payment": p, "app": p.application, "lines": presenters.receipt_lines(p), "paid_for": presenters.paid_for(p),
        "environment": _environment(), "charge": presenters.payer_charge(),
        "student_no": enrollment.student.student_no if enrollment else "", "back_url": reverse("web:staff-payment", args=[ref])})


# ---------------------------------------------------------------------------
# Staff accounts (admin)
# ---------------------------------------------------------------------------
@staff_required(admin=True)
def team(request):
    accounts.ensure_staff_profiles()
    qs = StaffProfile.objects.select_related("user").order_by("staff_no")
    q, dept = (request.GET.get("q") or "").strip(), request.GET.get("dept") or ""
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(title__icontains=q) | Q(email__icontains=q) | Q(staff_no__icontains=q))
    if dept:
        qs = qs.filter(department=dept)
    rows = [{"s": s, "access": accounts.staff_access(s)} for s in qs]
    return render(request, "web/staff/team.html", shell(
        request, "team", "Staff", "Team directory", rows=rows, q=q, dept=dept, departments=StaffProfile.Department.values))


def _form_data(cleaned):
    return {"fullName": cleaned["fullName"], "title": cleaned["title"], "department": cleaned["department"],
            "email": cleaned.get("email", ""), "phone": cleaned.get("phone", ""), "access": cleaned["access"],
            **({"status": cleaned["status"]} if cleaned.get("status") else {})}


@staff_required(admin=True)
def team_member(request, pk=None):
    profile = get_object_or_404(StaffProfile.objects.select_related("user"), pk=pk) if pk else None
    is_self = bool(profile and profile.user_id == request.user.pk)
    initial = {}
    if profile:
        initial = {"fullName": profile.full_name, "title": profile.title, "email": profile.email, "phone": profile.phone,
                   "department": profile.department, "access": accounts.staff_access(profile), "status": profile.status}
    form = StaffMemberForm(request.POST or None, initial=initial, editing=profile, is_self=is_self)
    if request.method == "POST" and request.POST.get("action") == "reset" and profile and profile.user_id:
        return _reset_password(request, profile)
    if request.method == "POST" and form.is_valid():
        data = _form_data(form.cleaned_data)
        try:
            with transaction.atomic():
                if profile:
                    if is_self:
                        data.pop("access", None)
                        data.pop("status", None)
                    if profile.user_id:
                        data.pop("email", None)
                    password = accounts.update_staff(profile, data, request.user)
                else:
                    profile, password = accounts.create_staff(data)
        except ServiceError as exc:
            if exc.field and exc.field in form.fields:
                form.add_error(exc.field, error_text(exc))
            else:
                form.add_error(None, error_text(exc))
        else:
            messages.success(request, f"{'Staff updated' if pk else 'Staff added'}: {profile.full_name}.")
            if password:
                return render(request, "web/staff/temp_password.html", shell(
                    request, "team", "Staff", "Team directory", name=profile.full_name, email=profile.email, password=password))
            return redirect("web:staff-team")
    return render(request, "web/staff/team_member.html", shell(
        request, "team", "Staff", "Team directory", form=form, profile=profile, is_self=is_self,
        access=accounts.staff_access(profile) if profile else ""))


def _reset_password(request, profile):
    user = profile.user
    if user.role == User.Role.ADMIN and not request.user.is_superuser and user != request.user:
        raise PermissionDenied("Only a superuser can reset another administrator's password.")
    password = temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    if user == request.user:
        update_session_auth_hash(request, user)
    return render(request, "web/staff/temp_password.html", shell(
        request, "team", "Staff", "Team directory", name=profile.full_name, email=user.email, password=password, reset=True))


# ---------------------------------------------------------------------------
# Settings (admin)
# ---------------------------------------------------------------------------
def _settings_forms(s, data=None, section=None):
    c = s.current_cohort
    initial = {
        "institution": {"name": s.institution_name, "short": s.short_name, "city": s.city, "address": s.address,
                        "phones": ", ".join(s.phones or []), "email": s.email, "website": s.website,
                        "directorName": s.director_name, "directorTitle": s.director_title},
        "admissions": {"intake": c.name if c else "", "opens": c and c.enrolment_opens, "closes": c and c.enrolment_closes,
                       "cohortDate": c and c.start_date, "earlyBirdDeadline": c and c.early_bird_deadline,
                       "applicationFee": s.application_fee, "acceptingApplications": s.accepting_applications,
                       "allowInstallments": s.allow_installments},
        "discounts": {"earlyBirdPct": s.early_bird_pct, "excellencePct": s.excellence_pct,
                      "excellenceMinYear": s.excellence_min_waec_year, "excellenceMinAs": s.excellence_min_as},
        "notifications": {"emailNotifications": s.email_notifications, "staffPaymentAlerts": s.staff_payment_alerts,
                          "staffApplicationAlerts": s.staff_application_alerts},
    }
    classes = {"institution": InstitutionForm, "admissions": AdmissionsForm, "discounts": DiscountsForm,
               "notifications": NotificationSettingsForm, "intake": IntakeForm}
    forms = {k: cls(data if k == section else None, initial=initial.get(k), prefix=k) for k, cls in classes.items()}
    return forms


@staff_required(admin=True)
def settings_view(request):
    s = SiteSettings.load()
    section = request.POST.get("section") if request.method == "POST" else None
    forms = _settings_forms(s, request.POST or None, section)
    if section in forms and forms[section].is_valid():
        d = forms[section].cleaned_data
        with transaction.atomic():
            if section == "institution":
                s.institution_name, s.short_name, s.city, s.address = d["name"], d["short"], d["city"], d["address"]
                s.phones, s.email, s.website = d["phones"], d["email"], d["website"]
                s.director_name, s.director_title = d["directorName"], d["directorTitle"] or s.director_title
            elif section == "admissions":
                c = s.current_cohort
                if c is None:
                    messages.error(request, "There is no current intake. Start a new intake first.")
                    return redirect("web:staff-settings")
                c.name, c.start_date = d["intake"], d["cohortDate"]
                c.enrolment_opens, c.enrolment_closes, c.early_bird_deadline = d["opens"], d["closes"], d["earlyBirdDeadline"]
                c.save()
                s.application_fee, s.accepting_applications = d["applicationFee"], d["acceptingApplications"]
                s.allow_installments = d["allowInstallments"]
            elif section == "discounts":
                s.early_bird_pct, s.excellence_pct = d["earlyBirdPct"], d["excellencePct"]
                s.excellence_min_waec_year, s.excellence_min_as = d["excellenceMinYear"], d["excellenceMinAs"]
            elif section == "notifications":
                s.email_notifications = d["emailNotifications"]
                s.staff_payment_alerts, s.staff_application_alerts = d["staffPaymentAlerts"], d["staffApplicationAlerts"]
            elif section == "intake":
                cohort = Cohort.objects.create(name=d["intake"], start_date=d["cohortDate"], enrolment_opens=d["opens"],
                                               enrolment_closes=d["closes"], early_bird_deadline=d["earlyBirdDeadline"])
                s.current_cohort = cohort
            s.save()
        messages.success(request, "New intake started." if section == "intake" else "Settings saved.")
        return redirect(f"{reverse('web:staff-settings')}#{section}")
    from django.conf import settings as dj

    gateway = {"name": dj.PAYMENT_GATEWAY, "environment": dj.ZAINPAY["ENVIRONMENT"], "payer_charge": dj.ZAINPAY["PAYER_CHARGE"],
               "channels": ", ".join(dj.ZAINPAY["CHANNELS"]).replace("bank_transfer", "Bank transfer"),
               "email": bool(dj.EMAIL_HOST_USER), "prefix": s.payment_ref_prefix}
    return render(request, "web/staff/settings.html", shell(
        request, "settings", "Settings", "Platform configuration", forms=forms, section=section, gateway=gateway))


# ---------------------------------------------------------------------------
# Notifications + search
# ---------------------------------------------------------------------------
@staff_required
def notifications(request):
    mine = Notification.objects.filter(recipient=request.user)
    if request.method == "POST":
        mine.filter(read=False).update(read=True)
        return redirect(request.POST.get("next") or "web:staff-notifications")
    page, query = paginate(request, mine)
    return render(request, "web/staff/notifications.html", shell(
        request, "notifications", "Notifications", "Updates for you", page=page, query=query))


@staff_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if request.method == "POST":
        n.read = True
        n.save(update_fields=["read"])
    link = n.link or reverse("web:staff-notifications")
    return redirect(link if link.startswith("/") else "/" + link)


@staff_required
def search(request):
    q = (request.GET.get("q") or "").strip()
    apps = students = pays = []
    if len(q) >= 2:
        apps = (Application.objects.select_related("programme")
                .filter(Q(number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                        | Q(email__icontains=q) | Q(user__email__icontains=q) | Q(phone__icontains=q))[:20])
        students = (Student.objects.filter(Q(student_no__icontains=q) | Q(first_name__icontains=q)
                                           | Q(last_name__icontains=q) | Q(email__icontains=q))
                    .prefetch_related("enrollments__application")[:20])
        pays = Payment.objects.filter(Q(reference__icontains=q) | Q(name__icontains=q)
                                      | Q(application__number__icontains=q))[:20]
    return render(request, "web/staff/search.html", shell(
        request, "search", "Search", "Applications, students and payments", q=q, apps=apps, students=students, pays=pays))


# ---------------------------------------------------------------------------
# Support tickets from students
# ---------------------------------------------------------------------------
@staff_required
def tickets(request):
    from apps.comms.models import SupportTicket

    status = request.GET.get("status") or "Open"
    qs = SupportTicket.objects.select_related("student").order_by("-created_at")
    counts = {s: qs.filter(status=s).count() for s in ("Open", "Resolved")}
    if status != "All":
        qs = qs.filter(status=status)
    page, query = paginate(request, qs)
    return render(request, "web/staff/tickets.html", shell(
        request, "support", "Support", "Student help desk", page=page, query=query, status=status, counts=counts))


@staff_required
def ticket_detail(request, pk):
    from apps.comms.models import SupportTicket
    from apps.comms.services import notify

    t = get_object_or_404(SupportTicket.objects.select_related("student__user", "student__guardian"), pk=pk)
    note = NoteForm(request.POST or None)
    if request.method == "POST":
        reply = (request.POST.get("reply") or "").strip()[:4000]
        if not reply:
            messages.error(request, "Write a reply first.")
        else:
            t.reply, t.replied_by, t.replied_at = reply, request.user, timezone.now()
            t.status = SupportTicket.Status.RESOLVED if request.POST.get("resolve") else SupportTicket.Status.OPEN
            t.save()
            notify(t.student.account, f"Reply to your ticket {t.number}", f"{t.subject}: {reply[:300]}",
                   Notification.Type.SUPPORT, link=f"student/{t.student.pk}/support/", email=True)
            messages.success(request, f"Reply sent to {t.student.full_name}.")
            return redirect("web:staff-ticket", pk=t.pk)
    return render(request, "web/staff/ticket.html", shell(request, "support", "Support", "Student help desk", t=t, form=note))
