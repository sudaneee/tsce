from django.urls import path

from . import views

urlpatterns = [
    path("enquiries", views.EnquiryCreateView.as_view(), name="enquiry-create"),
    path("announcements/public", views.PublicAnnouncementsView.as_view(), name="announcements-public"),
]
