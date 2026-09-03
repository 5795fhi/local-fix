from django.contrib import admin

from .models import Booking, BookingStatusHistory


class StatusHistoryInline(admin.TabularInline):
    model = BookingStatusHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "changed_by", "note", "created_at"]
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "provider", "category", "status", "quoted_price", "scheduled_for"]
    list_filter = ["status", "category"]
    search_fields = ["customer__email", "provider__email", "address"]
    date_hierarchy = "created_at"
    inlines = [StatusHistoryInline]


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ["booking", "from_status", "to_status", "changed_by", "created_at"]
    list_filter = ["to_status"]
