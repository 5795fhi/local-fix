from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.emails import send_booking_email
from accounts.models import ProviderProfile
from bookings.models import Booking
from notifications.models import Notification
from services.models import ServiceCategory

from .gateway import chat_completion
from .matching import (
    extract_datetime,
    format_provider_context,
    should_suggest_providers,
    suggest_providers,
)
from .models import Conversation, Message


def _can_book(user):
    return user.is_authenticated and user.is_customer


@login_required
def chat(request, conversation_id=None):
    conversations = request.user.conversations.all()
    conversation = None
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
    elif conversations.exists():
        conversation = conversations.first()

    return render(
        request,
        "assistant/chat.html",
        {
            "conversations": conversations,
            "conversation": conversation,
            "can_book": _can_book(request.user),
        },
    )


@login_required
@require_POST
def send_message(request):
    content = (request.POST.get("message") or "").strip()
    if not content:
        return JsonResponse({"error": "Message is required."}, status=400)

    conversation_id = request.POST.get("conversation_id")
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
    else:
        conversation = Conversation.objects.create(
            user=request.user, title=content[:60]
        )

    Message.objects.create(
        conversation=conversation, role=Message.Role.USER, content=content
    )

    history = [
        {"role": m.role, "content": m.content}
        for m in conversation.messages.all()
        if m.role in (Message.Role.USER, Message.Role.ASSISTANT)
    ]

    suggestions = []
    category = None
    suggested_for = None
    extra_system = ""
    if _can_book(request.user) and should_suggest_providers(content):
        category, suggestions = suggest_providers(request.user, content)
        extra_system = format_provider_context(category, suggestions)
        hinted = extract_datetime(content)
        if hinted and hinted > timezone.now():
            suggested_for = hinted

    reply = chat_completion(history, extra_system=extra_system)
    meta = {}
    if suggestions:
        meta = {
            "suggestions": suggestions,
            "category_id": category.pk if category else None,
            "category_name": category.name if category else "",
        }
        if suggested_for:
            meta["suggested_for"] = suggested_for.strftime("%Y-%m-%dT%H:%M")

    assistant_msg = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=reply,
        meta=meta,
    )
    conversation.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "conversation_id": conversation.id,
            "reply": assistant_msg.content,
            "created_at": assistant_msg.created_at.strftime("%H:%M"),
            "suggestions": suggestions,
            "suggested_for": meta.get("suggested_for", ""),
            "can_book": _can_book(request.user),
        }
    )


@login_required
@require_POST
def book_from_chat(request):
    if not _can_book(request.user):
        return JsonResponse(
            {"error": "Only customers can place a booking."}, status=403
        )
    if not request.user.is_verified and not request.user.is_superuser:
        return JsonResponse(
            {"error": "Please verify your account before booking."}, status=403
        )

    conversation_id = request.POST.get("conversation_id")
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )
    profile = get_object_or_404(
        ProviderProfile.objects.select_related("user").prefetch_related("categories"),
        pk=request.POST.get("provider_id"),
        is_approved=True,
        is_available=True,
    )
    if profile.user_id == request.user.id:
        return JsonResponse({"error": "You cannot book yourself."}, status=400)

    address = (request.POST.get("address") or "").strip()
    description = (request.POST.get("description") or "").strip()
    scheduled_raw = (request.POST.get("scheduled_for") or "").strip()
    if not address or not description or not scheduled_raw:
        return JsonResponse(
            {"error": "Address, job details, and date/time are required."},
            status=400,
        )

    try:
        naive = datetime.strptime(scheduled_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        return JsonResponse({"error": "Use a valid date and time."}, status=400)

    scheduled_for = timezone.make_aware(naive, timezone.get_current_timezone())
    if scheduled_for < timezone.now():
        return JsonResponse(
            {"error": "Please choose a future date and time."}, status=400
        )

    category_id = request.POST.get("category_id")
    category = None
    if category_id:
        category = profile.categories.filter(pk=category_id).first()
    if category is None:
        category = profile.categories.filter(is_active=True).first()
    if category is None:
        category = ServiceCategory.objects.filter(is_active=True).first()

    booking = Booking(
        customer=request.user,
        provider=profile.user,
        category=category,
        description=description,
        address=address,
        scheduled_for=scheduled_for,
        quoted_price=category.base_price if category else 0,
    )
    try:
        booking.full_clean()
        booking.save()
    except ValidationError as exc:
        msg = "; ".join(
            exc.messages if hasattr(exc, "messages") else [str(exc)]
        )
        return JsonResponse({"error": msg or "Could not create this booking."}, status=400)

    Notification.notify(
        profile.user,
        "New booking request",
        f"{request.user.display_name} requested {booking.category}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    send_booking_email("requested", booking)

    when = timezone.localtime(scheduled_for).strftime("%a %d %b, %H:%M")
    confirm = (
        f"Booking request #{booking.pk} sent to {profile.user.display_name} "
        f"for {when} at {address}. They’ll review it and send a quote. "
        f"You can track it under Bookings."
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=confirm,
        meta={"booking_id": booking.pk},
    )
    conversation.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "reply": confirm,
            "created_at": timezone.localtime().strftime("%H:%M"),
            "booking_id": booking.pk,
            "booking_url": reverse("bookings:detail", args=[booking.pk]),
        }
    )


@login_required
@require_POST
def new_conversation(request):
    conversation = Conversation.objects.create(user=request.user)
    return redirect("assistant:chat_detail", conversation_id=conversation.id)


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(
        Conversation, pk=conversation_id, user=request.user
    )
    conversation.delete()
    return redirect("assistant:chat")
