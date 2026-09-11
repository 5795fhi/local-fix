import hashlib

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import verified_required
from accounts.emails import send_booking_email
from bookings.models import Booking
from notifications.models import Notification
from .models import Payment


@verified_required
def checkout(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "category"), pk=booking_id
    )
    if request.user != booking.customer:
        raise PermissionDenied("Only the customer can pay for this booking.")
    if booking.status != Booking.Status.COMPLETED:
        messages.error(request, "This booking is not ready for payment.")
        return redirect("bookings:detail", pk=booking.pk)
    if hasattr(booking, "payment") and booking.payment.status == Payment.Status.SUCCEEDED:
        messages.info(request, "This booking is already paid.")
        return redirect("bookings:detail", pk=booking.pk)

    return render(
        request,
        "payments/checkout.html",
        {"booking": booking, "methods": Payment.Method.choices},
    )


@verified_required
@require_POST
def pay(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if request.user != booking.customer:
        raise PermissionDenied
    if booking.status != Booking.Status.COMPLETED:
        messages.error(request, "This booking is not ready for payment.")
        return redirect("bookings:detail", pk=booking.pk)

    method = request.POST.get("method", Payment.Method.CARD)
    if method not in Payment.Method.values:
        method = Payment.Method.CARD

    # Idempotency: a stable key per booking+customer prevents double charges on
    # duplicate submits/retries. Amounts are recomputed server-side, never trusted
    # from the client.
    idem = hashlib.sha256(
        f"booking:{booking.pk}:user:{request.user.pk}".encode()
    ).hexdigest()
    amount = booking.quoted_price
    fee = booking.platform_fee
    payout = booking.provider_payout

    with transaction.atomic():
        payment, created = Payment.objects.select_for_update().get_or_create(
            idempotency_key=idem,
            defaults={
                "booking": booking,
                "payer": request.user,
                "amount": amount,
                "platform_fee": fee,
                "provider_payout": payout,
                "method": method,
            },
        )
        if payment.status == Payment.Status.SUCCEEDED:
            messages.info(request, "Payment already processed.")
            return redirect("bookings:detail", pk=booking.pk)

        # Mock gateway authorization always succeeds in this build.
        payment.method = method
        payment.status = Payment.Status.SUCCEEDED
        payment.paid_at = timezone.now()
        payment.save()

        if booking.can_transition_to(Booking.Status.PAID):
            booking.transition_to(Booking.Status.PAID, actor=request.user)

    Notification.notify(
        booking.provider,
        "Payment received",
        f"You earned {payout} from booking #{booking.pk}.",
        url=reverse("bookings:detail", args=[booking.pk]),
    )
    send_booking_email("paid", booking)
    messages.success(request, f"Payment of {amount} successful. Reference {payment.reference}.")
    return redirect("bookings:detail", pk=booking.pk)


@verified_required
def receipt(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)
    if request.user not in (booking.customer, booking.provider) and not request.user.is_platform_admin:
        raise PermissionDenied
    payment = get_object_or_404(Payment, booking=booking)
    return render(request, "payments/receipt.html", {"payment": payment, "booking": booking})
