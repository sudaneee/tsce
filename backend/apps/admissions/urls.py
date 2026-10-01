from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("applications", views.ApplicationsView.as_view(), name="applications"),
    # Numbers contain slashes (TSCE/APP/2026/00001), hence <path:>.
    path("staff/summary", staff_views.StaffSummaryView.as_view(), name="staff-summary"),
    path("staff/search", staff_views.StaffSearchView.as_view(), name="staff-search"),
    path("staff/applications", staff_views.StaffApplicationsView.as_view(), name="staff-applications"),
    path("staff/applications/<path:number>/reject", staff_views.RejectApplicationView.as_view(), name="staff-application-reject"),
    path("staff/applications/<path:number>/remind", staff_views.RemindView.as_view(), name="staff-application-remind"),
    path("staff/applications/<path:number>/waec-file", staff_views.WaecFileView.as_view(), name="staff-application-waec"),
    path("staff/applications/<path:number>/award", views.AwardDecisionView.as_view(), name="application-award"),
    path("staff/applications/<path:number>", staff_views.StaffApplicationDetailView.as_view(), name="staff-application-detail"),
    path("applications/<path:number>", views.ApplicationDetailView.as_view(), name="application-detail"),
]
