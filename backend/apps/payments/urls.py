from django.urls import path

from . import views

urlpatterns = [
    path("payments/initialize", views.InitializePaymentView.as_view(), name="payment-initialize"),
    path("payments/zainpay/callback", views.zainpay_callback, name="zainpay-callback"),
    path("payments/zainpay/webhook", views.zainpay_webhook, name="zainpay-webhook"),
    path("payments/simulator/<str:ref>", views.simulator_checkout, name="payment-simulator"),
    path("payments/<str:ref>/check", views.PaymentCheckView.as_view(), name="payment-check"),
    path("payments/<str:ref>", views.PaymentDetailView.as_view(), name="payment-detail"),
]
