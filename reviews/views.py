from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import verified_required
from bookings.models import Booking
from notifications.models import Notification
from .forms import ReviewForm


@verified_required
def leave_review(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("provider"), pk=booking_id
    )
    if request.user != booking.customer:
        raise PermissionDenied("Only the customer can review this booking.")
    if not booking.is_reviewable:
        messages.error(request, "This booking cannot be reviewed yet.")
        return redirect("bookings:detail", pk=booking.pk)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.customer = request.user
            review.provider = booking.provider
            review.save()
            Notification.notify(
                booking.provider,
                "New review",
                f"{request.user.display_name} rated you {review.rating}/5.",
                url=reverse("bookings:detail", args=[booking.pk]),
            )
            messages.success(request, "Thanks for your feedback!")
            return redirect("bookings:detail", pk=booking.pk)
    else:
        form = ReviewForm()
    return render(request, "reviews/leave_review.html", {"form": form, "booking": booking})
