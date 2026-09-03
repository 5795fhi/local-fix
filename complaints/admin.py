from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "raised_by", "status", "handled_by", "created_at"]
    list_filter = ["status"]
    search_fields = ["subject", "description", "raised_by__email"]
