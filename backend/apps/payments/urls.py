from django.urls import path

from . import views

urlpatterns = [
    path("payments/zainpay/callback", views.zainpay_callback, name="zainpay-callback"),
    path("payments/zainpay/webhook", views.zainpay_webhook, name="zainpay-webhook"),
    path("payments/simulator/<str:ref>", views.simulator_checkout, name="payment-simulator"),
]
