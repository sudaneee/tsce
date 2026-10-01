from django.contrib import admin

from .models import Application, ApplicationEvent, AwardRequest


class ApplicationEventInline(admin.TabularInline):
    model = ApplicationEvent
    extra = 0
    readonly_fields = ["at", "text", "ok", "actor"]
    can_delete = False


class AwardRequestInline(admin.StackedInline):
    model = AwardRequest
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["number", "full_name", "programme", "cohort", "amount_payable", "status", "payment_status", "created_at"]
    list_filter = ["status", "payment_status", "cohort", "programme", "discount_type"]
    search_fields = ["number", "first_name", "last_name", "email", "phone"]
    date_hierarchy = "created_at"
    readonly_fields = ["number", "created_at", "updated_at", "paid_at"]
    autocomplete_fields = ["user"]
    list_select_related = ["programme", "cohort"]
    inlines = [AwardRequestInline, ApplicationEventInline]


@admin.register(AwardRequest)
class AwardRequestAdmin(admin.ModelAdmin):
    list_display = ["application", "type", "requested_pct", "awarded_pct", "status", "reviewed_by", "reviewed_at"]
    list_filter = ["type", "status"]
    search_fields = ["application__number", "application__first_name", "application__last_name"]
    raw_id_fields = ["application"]
