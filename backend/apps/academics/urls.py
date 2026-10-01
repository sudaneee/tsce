from django.urls import path

from . import views

urlpatterns = [
    path("certificates/verify", views.CertificateVerifyView.as_view(), name="certificate-verify"),
]
