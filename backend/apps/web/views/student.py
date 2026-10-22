"""
The student portal (Phase 7), server-rendered. A self-applicant signs in as the
student; a parent opens the portal for each child. Results and the certificate
are withheld until the programme fee is paid in full.
"""
from functools import wraps
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.academics import services as academics
from apps.academics.models import Student
from apps.accounts.models import User
from apps.comms.models import Announcement, Notification, SupportTicket
from apps.comms.services import notify_staff
from apps.core.models import Sequence
from apps.core.validators import normalize_ng_phone
from apps.payments.models import Payment

from .. import presenters
from ..forms import StyledForm
from .common import LOGIN_URL


def _students(user):
    return Student.objects.filter(Q(user=user) | Q(guardian=user))


def portal_required(view):
    @wraps(view)
    def wrapper(request, pk=None, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect(f"{LOGIN_URL}?{urlencode({'next': request.get_full_path()})}")
        if user.is_portal_staff:
            return redirect("/staff/")
        if user.must_change_password:
            return redirect(f"/account/password/?{urlencode({'next': request.get_full_path()})}")
        if pk is None:
            return view(request, *args, **kwargs)
        student = get_object_or_404(_students(user), pk=pk)
        enrollment = (student.enrollments.select_related("programme", "cohort", "application", "programme__instructor")
                      .order_by("-start_date").first())
        if enrollment is None:
            return redirect("/my-applications/")
        return view(request, student, enrollment, *args, **kwargs)
    return wrapper


def shell(request, student, enrollment, active, title, subtitle, **ctx):
    mine = Notification.objects.filter(recipient=request.user)
    return {"student": student, "enrollment": enrollment, "app": enrollment.application, "programme": enrollment.programme,
            "active": active, "page_title": title, "page_sub": subtitle, "bell": list(mine[:8]),
            "unread": mine.filter(read=False).count(), "is_parent": request.user.role == User.Role.PARENT,
            "siblings": _students(request.user).exclude(pk=student.pk) if request.user.role == User.Role.PARENT else [],
            "charge": presenters.payer_charge(), **ctx}


@portal_required
def home(request):
    """/student/: straight to the student's portal, or a chooser for a parent with several children."""
    kids = list(_students(request.user).filter(enrollments__isnull=False).distinct())
    if len(kids) == 1:
        return redirect("web:student-dashboard", pk=kids[0].pk)
    if not kids:
        return redirect("/my-applications/")
    return render(request, "web/student/choose.html", {"kids": kids})


@portal_required
def dashboard(request, student, enrollment):
    att, res = academics.attendance(enrollment), academics.results(enrollment)
    cert = academics.certificate_status(enrollment)
    news = Announcement.objects.filter(status=Announcement.Status.PUBLISHED,
                                       audience__in=[Announcement.Audience.PUBLIC, Announcement.Audience.STUDENTS])[:3]
    today = timezone.localdate()
    return render(request, "web/student/dashboard.html", shell(
        request, student, enrollment, "dashboard", "Dashboard", "Your learning at a glance",
        att=att, res=res, cert=cert, news=news, started=enrollment.start_date <= today,
        days_to_start=(enrollment.start_date - today).days))


@portal_required
def programme(request, student, enrollment):
    return render(request, "web/student/programme.html", shell(
        request, student, enrollment, "programme", "My Programme", "Modules & progress",
        modules=enrollment.module_progress()))


@portal_required
def attendance(request, student, enrollment):
    return render(request, "web/student/attendance.html", shell(
        request, student, enrollment, "attendance", "Attendance", "Class attendance",
        att=academics.attendance(enrollment), minimum=academics.MIN_ATTENDANCE_PCT))


@portal_required
def results(request, student, enrollment):
    return render(request, "web/student/results.html", shell(
        request, student, enrollment, "results", "Results", "Assessments & grades", res=academics.results(enrollment)))


@portal_required
def certificate(request, student, enrollment):
    return render(request, "web/student/certificate.html", shell(
        request, student, enrollment, "certificate", "Certificate", "Completion & verification",
        cert=academics.certificate_status(enrollment)))


@portal_required
def payments(request, student, enrollment):
    app = enrollment.application
    rows = app.payments.filter(status__in=[Payment.Status.SUCCESS, Payment.Status.REFUNDED, Payment.Status.PENDING]).order_by("-created_at")
    return render(request, "web/student/payments.html", shell(
        request, student, enrollment, "payments", "Payments", "Fees & receipts", rows=rows,
        app_fee=presenters.application_fee_due(app)))


@portal_required
def announcements(request, student, enrollment):
    items = Announcement.objects.filter(status=Announcement.Status.PUBLISHED,
                                        audience__in=[Announcement.Audience.PUBLIC, Announcement.Audience.STUDENTS])[:50]
    return render(request, "web/student/announcements.html", shell(
        request, student, enrollment, "announcements", "Announcements", "News & notices", items=items))


class TicketForm(StyledForm):
    category = forms.ChoiceField(choices=SupportTicket.Category.choices)
    subject = forms.CharField(max_length=150)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5, "class": "textarea"}))


@portal_required
def support(request, student, enrollment):
    form = TicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        t = SupportTicket.objects.create(number=f"TKT-{1000 + Sequence.next('ticket')}", student=student, **form.cleaned_data)
        notify_staff("New support ticket", f"{student.full_name} ({student.student_no}): {t.subject}", Notification.Type.SUPPORT,
                     link=reverse("web:staff-ticket", args=[t.pk]))
        messages.success(request, f"Ticket {t.number} sent — the TSCE team will reply here.")
        return redirect("web:student-support", pk=student.pk)
    return render(request, "web/student/support.html", shell(
        request, student, enrollment, "support", "Support", "Help desk", form=form, tickets=student.tickets.all()))


class ProfileForm(StyledForm):
    phone = forms.CharField(max_length=30)
    email = forms.EmailField(required=False, label="Email (optional)")
    address = forms.CharField(max_length=300, required=False)
    state = forms.CharField(max_length=40, required=False)
    lga = forms.CharField(max_length=80, required=False, label="LGA")
    emergency_contact = forms.CharField(max_length=200, required=False, label="Emergency contact (name and phone)")

    def clean_phone(self):
        return normalize_ng_phone(self.cleaned_data["phone"])


@portal_required
def profile(request, student, enrollment):
    fields = ["phone", "email", "address", "state", "lga", "emergency_contact"]
    form = ProfileForm(request.POST or None, initial={f: getattr(student, f) for f in fields})
    if request.method == "POST" and form.is_valid():
        for f in fields:
            setattr(student, f, form.cleaned_data[f])
        student.save(update_fields=[*fields, "updated_at"])
        messages.success(request, "Profile updated.")
        return redirect("web:student-profile", pk=student.pk)
    return render(request, "web/student/profile.html", shell(
        request, student, enrollment, "profile", "Profile", "Personal information", form=form))
