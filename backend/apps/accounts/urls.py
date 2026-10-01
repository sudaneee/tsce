from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="register"),
    path("auth/verify-email", views.VerifyEmailView.as_view(), name="verify-email"),
    path("auth/resend-verification", views.ResendVerificationView.as_view(), name="resend-verification"),
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("auth/change-password", views.ChangePasswordView.as_view(), name="change-password"),
    path("staff/staff", staff_views.StaffListView.as_view(), name="staff-list"),
    path("staff/staff/<int:pk>", staff_views.StaffDetailView.as_view(), name="staff-detail"),
    path("staff/users/<int:pk>/reset-password", views.AdminResetPasswordView.as_view(), name="admin-reset-password"),
]
