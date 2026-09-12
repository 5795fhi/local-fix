from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bookings.models import BookingStatusHistory

from accounts.decorators import verified_required
from accounts.emails import send_booking_email, send_negotiation_email
from accounts.models import ProviderProfile
from notifications.models import Notification
from .forms import BookingForm, CancelForm, DeclineOfferForm, OfferForm, QuoteForm
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
            send_booking_email("requested", booking)
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
    is_customer = request.user == booking.customer
    context = {
        "booking": booking,
        "history": booking.history.select_related("changed_by"),
        "quote_form": QuoteForm(initial={"quoted_price": booking.quoted_price}),
        "offer_form": OfferForm(initial={"quoted_price": booking.quoted_price}),
        "counter_form": DeclineOfferForm(initial={"counter_price": booking.quoted_price}),
        "cancel_form": CancelForm(),
        "payment": getattr(booking, "payment", None),
        "me_role": "customer" if is_customer else "provider",
        "other_party": booking.provider if is_customer else booking.customer,
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
        send_booking_email("accepted", booking)
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


# --- Price negotiation --------------------------------------------------------


def _negotiation_guard(request, booking):
    """Return (ok, error_response) for negotiation actions on a booking."""
    _require_participant(booking, request.user)
    if booking.status != Booking.Status.ACCEPTED:
        messages.error(request, "This booking can no longer be renegotiated.")
        return False, redirect("bookings:detail", pk=booking.pk)
    return True, None


@verified_required
@require_POST
def offer_price(request, pk):
    """Let the customer make the first negotiation offer after the quote."""
    booking = get_object_or_404(Booking, pk=pk)
    ok, resp = _negotiation_guard(request, booking)
    if not ok:
        return resp
    if request.user != booking.customer or booking.last_offer_by:
        messages.error(request, "You can only make a new offer after the professional has quoted a price.")
        return redirect("bookings:detail", pk=pk)
    form = OfferForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid offer amount.")
        return redirect("bookings:detail", pk=pk)

    booking.quoted_price = form.cleaned_data["quoted_price"]
    booking.last_offer_by = "customer"
    note = form.cleaned_data.get("note", "")
    if note:
        booking.provider_note = note
    booking.save(update_fields=["quoted_price", "last_offer_by", "provider_note", "updated_at"])

    BookingStatusHistory.objects.create(
        booking=booking,
        from_status=booking.status,
        to_status=booking.status,
        changed_by=request.user,
        note=f"Price offer ₹{booking.quoted_price:,.0f} — {note}" if note else f"Price offer ₹{booking.quoted_price:,.0f}",
    )

    other = booking.provider if request.user == booking.customer else booking.customer
    Notification.notify(
        other,
        f"New price offer: ₹{booking.quoted_price:,.0f}",
        f"{request.user.display_name} proposed ₹{booking.quoted_price:,.0f} for booking #{booking.pk}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    send_negotiation_email(booking, offer_by=request.user, note=note)
    messages.success(request, f"Offer of ₹{booking.quoted_price:,.0f} sent.")
    return redirect("bookings:detail", pk=pk)


@verified_required
@require_POST
def accept_offer(request, pk):
    """The non-offering party locks the current quoted price."""
    booking = get_object_or_404(Booking, pk=pk)
    ok, resp = _negotiation_guard(request, booking)
    if not ok:
        return resp
    if not booking.last_offer_by or booking.last_offer_by == (
        "customer" if request.user == booking.customer else "provider"
    ):
        messages.error(request, "There is no pending offer from the other party to accept.")
        return redirect("bookings:detail", pk=pk)

    BookingStatusHistory.objects.create(
        booking=booking,
        from_status=booking.status,
        to_status=booking.status,
        changed_by=request.user,
        note=f"Offer of ₹{booking.quoted_price:,.0f} accepted — final agreed price",
    )
    booking.last_offer_by = ""
    booking.save(update_fields=["last_offer_by", "updated_at"])

    other = booking.provider if request.user == booking.customer else booking.customer
    Notification.notify(
        other,
        f"Offer accepted: ₹{booking.quoted_price:,.0f}",
        f"{request.user.display_name} accepted ₹{booking.quoted_price:,.0f} as the final price for booking #{booking.pk}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    send_negotiation_email(booking, offer_by=request.user, accepted=True)
    messages.success(request, f"Deal — ₹{booking.quoted_price:,.0f} is the final agreed price.")
    return redirect("bookings:detail", pk=pk)


@verified_required
@require_POST
def decline_offer(request, pk):
    """Reject the pending offer and counter with a different price."""
    booking = get_object_or_404(Booking, pk=pk)
    ok, resp = _negotiation_guard(request, booking)
    if not ok:
        return resp
    if not booking.last_offer_by or booking.last_offer_by == (
        "customer" if request.user == booking.customer else "provider"
    ):
        messages.error(request, "There is no pending offer from the other party to decline.")
        return redirect("bookings:detail", pk=pk)

    form = DeclineOfferForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter your counter-offer amount.")
        return redirect("bookings:detail", pk=pk)

    old = booking.quoted_price
    booking.quoted_price = form.cleaned_data["counter_price"]
    booking.last_offer_by = "customer" if request.user == booking.customer else "provider"
    note = form.cleaned_data.get("note", "")
    if note:
        booking.provider_note = note
    booking.save(update_fields=["quoted_price", "last_offer_by", "provider_note", "updated_at"])

    BookingStatusHistory.objects.create(
        booking=booking,
        from_status=booking.status,
        to_status=booking.status,
        changed_by=request.user,
        note=f"Declined ₹{old:,.0f}, countered ₹{booking.quoted_price:,.0f}"
        + (f" — {note}" if note else ""),
    )

    other = booking.provider if request.user == booking.customer else booking.customer
    Notification.notify(
        other,
        f"Counter-offer: ₹{booking.quoted_price:,.0f}",
        f"{request.user.display_name} declined ₹{old:,.0f} and countered ₹{booking.quoted_price:,.0f} on booking #{booking.pk}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    send_negotiation_email(
        booking, offer_by=request.user, note=note,
        declined_old=old,
    )
    messages.success(request, f"Counter-offer of ₹{booking.quoted_price:,.0f} sent.")
    return redirect("bookings:detail", pk=pk)


@verified_required
@require_POST
def start_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    result = _simple_transition(
        request, pk, Booking.Status.IN_PROGRESS, "provider",
        "Job marked as in progress.", "customer",
        "Work started", "Your provider has started the job.",
    )
    if request.method == "POST" and booking.status == Booking.Status.IN_PROGRESS:
        send_booking_email("started", booking)
    return result


@verified_required
@require_POST
def complete_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    result = _simple_transition(
        request, pk, Booking.Status.COMPLETED, "provider",
        "Job marked complete. Awaiting payment.", "customer",
        "Job completed", "Your job is complete. Please proceed to payment.",
    )
    if request.method == "POST" and booking.status == Booking.Status.COMPLETED:
        send_booking_email("completed", booking)
    return result


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
    send_booking_email(
        "rejected", booking, extra_note=booking.cancel_reason or ""
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
    send_booking_email(
        "cancelled", booking, actor=request.user,
        extra_note=booking.cancel_reason or "",
    )
    messages.info(request, "Booking cancelled.")
    return redirect("bookings:detail", pk=pk)
