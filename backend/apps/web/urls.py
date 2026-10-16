from django.urls import path, re_path

from .views import applicant, apply, auth

app_name = "web"

urlpatterns = [
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

    # Old addresses of these pages
    re_path(r"^pages/(?P<page>login|register|verify-email|application|my-applications|payment|success)\.html$",
            applicant.legacy, name="legacy"),
]
