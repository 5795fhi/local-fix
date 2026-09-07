from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "booking", "payer", "amount", "provider_payout", "status", "created_at"]
    list_filter = ["status", "method"]
    search_fields = ["reference", "payer__email"]
    readonly_fields = ["reference", "idempotency_key", "created_at", "paid_at"]
