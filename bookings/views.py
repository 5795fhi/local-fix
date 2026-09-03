from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.decorators import verified_required
from accounts.models import ProviderProfile
from notifications.models import Notification
from .forms import BookingForm, CancelForm, QuoteForm
from .models import Booking

User = get_user_model()


def _require_participant(booking, user):
    if user != booking.customer and user != booking.provider and not user.is_platform_admin:
        raise PermissionDenied("You are not part of this booking.")


@verified_required
def create_booking(request, provider_id):
    provider_profile = get_object_or_404(
        ProviderProfile.objects.select_related("user"),
        pk=provider_id,
        is_approved=True,
    )
    if request.user == provider_profile.user:
        messages.error(request, "You cannot book yourself.")
        return redirect("services:provider_detail", pk=provider_id)

    if request.method == "POST":
        form = BookingForm(request.POST)
        form.fields["category"].queryset = provider_profile.categories.all()
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.provider = provider_profile.user
            booking.quoted_price = booking.category.base_price if booking.category else 0
            booking.save()
            Notification.notify(
                provider_profile.user,
                "New booking request",
                f"{request.user.display_name} requested {booking.category}.",
                url=reverse("bookings:detail", args=[booking.pk]),
            )
            messages.success(request, "Booking request sent to the provider.")
            return redirect("bookings:detail", pk=booking.pk)
    else:
        form = BookingForm()
        form.fields["category"].queryset = provider_profile.categories.all()

    return render(
        request,
        "bookings/create.html",
        {"form": form, "provider": provider_profile},
    )


@verified_required
def booking_list(request):
    user = request.user
    if user.is_provider:
        qs = user.bookings_received.all()
    else:
        qs = user.bookings_made.all()
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    qs = qs.select_related("customer", "provider", "category")
    return render(
        request,
        "bookings/list.html",
        {"bookings": qs, "statuses": Booking.Status.choices, "active_status": status},
    )


@verified_required
def booking_detail(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related("customer", "provider", "category"),
        pk=pk,
    )
    _require_participant(booking, request.user)
    context = {
        "booking": booking,
        "history": booking.history.select_related("changed_by"),
        "quote_form": QuoteForm(initial={"quoted_price": booking.quoted_price}),
        "cancel_form": CancelForm(),
        "payment": getattr(booking, "payment", None),
    }
    return render(request, "bookings/detail.html", context)


@verified_required
@require_POST
def accept_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.user != booking.provider:
        raise PermissionDenied
    form = QuoteForm(request.POST)
    if form.is_valid():
        booking.quoted_price = form.cleaned_data["quoted_price"]
        try:
            booking.transition_to(
                Booking.Status.ACCEPTED,
                actor=request.user,
                note=form.cleaned_data.get("provider_note", ""),
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("bookings:detail", pk=pk)
        Notification.notify(
            booking.customer,
            "Booking accepted",
            f"{request.user.display_name} accepted your request for {booking.quoted_price}.",
            url=reverse("bookings:detail", args=[booking.pk]),
        )
        messages.success(request, "Booking accepted and quote sent.")
    else:
        messages.error(request, "Please provide a valid quote.")
    return redirect("bookings:detail", pk=pk)


def _simple_transition(request, pk, target, allowed_actor, success_msg, notify_to, notify_title, notify_body):
    booking = get_object_or_404(Booking, pk=pk)
    if allowed_actor == "provider" and request.user != booking.provider:
        raise PermissionDenied
    if allowed_actor == "customer" and request.user != booking.customer:
        raise PermissionDenied
    try:
        booking.transition_to(target, actor=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect("bookings:detail", pk=pk)
    recipient = booking.customer if notify_to == "customer" else booking.provider
    Notification.notify(
        recipient, notify_title, notify_body,
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    messages.success(request, success_msg)
    return redirect("bookings:detail", pk=pk)


@verified_required
@require_POST
def start_booking(request, pk):
    return _simple_transition(
        request, pk, Booking.Status.IN_PROGRESS, "provider",
        "Job marked as in progress.", "customer",
        "Work started", "Your provider has started the job.",
    )


@verified_required
@require_POST
def complete_booking(request, pk):
    return _simple_transition(
        request, pk, Booking.Status.COMPLETED, "provider",
        "Job marked complete. Awaiting payment.", "customer",
        "Job completed", "Your job is complete. Please proceed to payment.",
    )


@verified_required
@require_POST
def reject_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.user != booking.provider:
        raise PermissionDenied
    try:
        booking.transition_to(
            Booking.Status.REJECTED, actor=request.user,
            reason=request.POST.get("reason", ""),
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect("bookings:detail", pk=pk)
    Notification.notify(
        booking.customer, "Booking declined",
        f"{booking.provider.display_name} declined your request.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    messages.info(request, "Booking declined.")
    return redirect("bookings:detail", pk=pk)


@verified_required
@require_POST
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    _require_participant(booking, request.user)
    form = CancelForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    try:
        booking.transition_to(
            Booking.Status.CANCELLED, actor=request.user, reason=reason
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        return redirect("bookings:detail", pk=pk)
    other = booking.provider if request.user == booking.customer else booking.customer
    Notification.notify(
        other, "Booking cancelled",
        f"{request.user.display_name} cancelled booking #{booking.pk}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    messages.info(request, "Booking cancelled.")
    return redirect("bookings:detail", pk=pk)
