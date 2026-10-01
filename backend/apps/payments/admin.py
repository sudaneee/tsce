from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "purpose", "kind", "name", "amount", "status", "channel", "gateway", "created_at"]
    list_filter = ["status", "purpose", "kind", "channel", "gateway"]
    search_fields = ["reference", "gateway_ref", "name", "email", "application__number"]
    date_hierarchy = "created_at"
    raw_id_fields = ["application", "parent", "user", "verified_by"]
    # Money records change through the payment services, not by hand.
    readonly_fields = ["reference", "kind", "purpose", "amount", "fee", "discount", "gateway", "gateway_ref", "gateway_payload",
                       "created_at", "updated_at", "verified_at", "refunded_at"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["received_at", "gateway", "event_type", "reference", "signature_valid", "processed"]
    list_filter = ["gateway", "signature_valid", "processed"]
    search_fields = ["reference"]
    readonly_fields = [f.name for f in WebhookEvent._meta.fields]

    def has_add_permission(self, request):
        return False
