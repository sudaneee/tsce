from django.contrib import admin

from .models import Announcement, Enquiry, Notification, SupportTicket


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience", "tag", "pinned", "status", "published_at"]
    list_filter = ["audience", "status", "pinned"]
    search_fields = ["title", "body"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "recipient", "type", "title", "read"]
    list_filter = ["type", "read"]
    search_fields = ["recipient__email", "title"]
    raw_id_fields = ["recipient"]


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["number", "student", "category", "priority", "subject", "status", "created_at"]
    list_filter = ["status", "category", "priority"]
    search_fields = ["number", "subject", "student__first_name", "student__last_name"]
    raw_id_fields = ["student", "replied_by"]


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "name", "email", "phone", "programme", "subject", "status"]
    list_filter = ["status"]
    search_fields = ["name", "email", "subject", "message"]
