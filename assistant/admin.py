from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "updated_at"]
    search_fields = ["title", "user__email"]
    inlines = [MessageInline]
