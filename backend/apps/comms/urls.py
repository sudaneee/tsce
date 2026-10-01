from django.urls import path

from . import views

urlpatterns = [
    path("enquiries", views.EnquiryCreateView.as_view(), name="enquiry-create"),
    path("notifications", views.MyNotificationsView.as_view(), name="notifications"),
    path("notifications/read-all", views.MarkNotificationReadView.as_view(), name="notifications-read-all"),
    path("notifications/<int:pk>/read", views.MarkNotificationReadView.as_view(), name="notification-read"),
    path("announcements/public", views.PublicAnnouncementsView.as_view(), name="announcements-public"),
]
