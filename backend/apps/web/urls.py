from django.urls import path, re_path

from .views import applicant, apply, auth, public, staff

app_name = "web"

urlpatterns = [
    # The public website, at its usual addresses
    path("", public.home, name="home"),
    path("index.html", public.home),
    path("pages/about.html", public.about, name="about"),
    path("pages/programmes.html", public.programmes, name="programmes"),
    path("pages/admissions.html", public.admissions, name="admissions"),
    path("pages/news.html", public.news, name="news"),
    path("pages/contact.html", public.contact, name="contact"),
    path("pages/verify.html", public.verify, name="verify"),

    path("account/login/", auth.login_view, name="login"),
    path("account/register/", auth.register_view, name="register"),
    path("account/verify-email/", auth.verify_email_view, name="verify-email"),
    path("account/resend-verification/", auth.resend_verification_view, name="resend-verification"),
    path("account/logout/", auth.logout_view, name="logout"),
    path("account/password/", auth.password_view, name="password"),

    path("apply/", apply.apply_start, name="apply"),
    path("apply/<int:step>/", apply.apply_step, name="apply-step"),
    path("apply/done/<path:number>/", apply.apply_done, name="apply-done"),

    path("my-applications/", applicant.my_applications, name="my-applications"),
    path("pay/<path:number>/", applicant.pay, name="pay"),
    path("payments/<str:ref>/", applicant.payment_status, name="payment"),
    path("payments/<str:ref>/check/", applicant.payment_check, name="payment-check"),
    path("payments/<str:ref>/receipt/", applicant.receipt, name="receipt"),

    path("staff/", staff.dashboard, name="staff-dashboard"),
    path("staff/applications/", staff.applications, name="staff-applications"),
    path("staff/applications/<path:number>/", staff.application_detail, name="staff-application"),
    path("staff/waec/<path:number>/", staff.waec_file, name="staff-waec"),
    path("staff/awards/", staff.awards, name="staff-awards"),
    path("staff/payments/", staff.payments_list, name="staff-payments"),
    path("staff/payments/<str:ref>/", staff.payment_detail, name="staff-payment"),
    path("staff/payments/<str:ref>/receipt/", staff.staff_receipt, name="staff-receipt"),
    path("staff/team/", staff.team, name="staff-team"),
    path("staff/team/new/", staff.team_member, name="staff-team-new"),
    path("staff/team/<int:pk>/", staff.team_member, name="staff-team-member"),
    path("staff/settings/", staff.settings_view, name="staff-settings"),
    path("staff/notifications/", staff.notifications, name="staff-notifications"),
    path("staff/notifications/<int:pk>/", staff.notification_open, name="staff-notification"),
    path("staff/search/", staff.search, name="staff-search"),

    # Old addresses of these pages
    re_path(r"^pages/(?P<page>login|register|verify-email|application|my-applications|payment|success)\.html$",
            applicant.legacy, name="legacy"),
    re_path(r"^pages/staff/(?P<page>dashboard|applications|scholarships|payments|staff|settings)\.html$",
            applicant.legacy_staff, name="legacy-staff"),
]
