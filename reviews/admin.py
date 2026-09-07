from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["provider", "customer", "rating", "created_at"]
    list_filter = ["rating"]
    search_fields = ["provider__email", "customer__email", "comment"]
