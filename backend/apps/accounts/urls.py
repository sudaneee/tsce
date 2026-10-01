from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("auth/change-password", views.ChangePasswordView.as_view(), name="change-password"),
    path("staff/users/<int:pk>/reset-password", views.AdminResetPasswordView.as_view(), name="admin-reset-password"),
]
