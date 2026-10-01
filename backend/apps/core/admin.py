from django.contrib import admin

from .models import Sequence, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Institution", {"fields": ["institution_name", "short_name", "address", "city", "phones", "email", "website"]}),
        ("Certificates", {"fields": ["director_name", "director_title"]}),
        ("Admissions", {"fields": ["current_cohort", "accepting_applications", "application_fee"]}),
        ("Discounts (%)", {"fields": ["early_bird_pct", "excellence_pct", "excellence_min_waec_year", "excellence_min_as"]}),
        ("Payments", {"fields": ["payment_ref_prefix", "allow_card", "allow_transfer"]}),
        ("Notifications", {"fields": ["email_notifications", "staff_payment_alerts", "staff_application_alerts"]}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ["name", "value"]
