from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Booking(models.Model):
    """A service request moving through the booking lifecycle.

    State machine:
        REQUESTED --accept--> ACCEPTED --start--> IN_PROGRESS --complete--> COMPLETED
        REQUESTED/ACCEPTED --reject/cancel--> REJECTED / CANCELLED
        COMPLETED --pay--> PAID
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    # Allowed transitions keyed by current status.
    TRANSITIONS = {
        Status.REQUESTED: {Status.ACCEPTED, Status.REJECTED, Status.CANCELLED},
        Status.ACCEPTED: {Status.IN_PROGRESS, Status.CANCELLED},
        Status.IN_PROGRESS: {Status.COMPLETED, Status.CANCELLED},
        Status.COMPLETED: {Status.PAID},
        Status.PAID: set(),
        Status.REJECTED: set(),
        Status.CANCELLED: set(),
    }

    OPEN_STATUSES = {Status.REQUESTED, Status.ACCEPTED, Status.IN_PROGRESS}

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_made",
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings_received",
    )
    category = models.ForeignKey(
        "services.ServiceCategory",
        on_delete=models.SET_NULL,
        null=True,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED
    )
    description = models.TextField(help_text="What needs to be done.")
    address = models.CharField(max_length=255)
    scheduled_for = models.DateTimeField()
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    provider_note = models.TextField(blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["provider", "status"]),
        ]

    def __str__(self):
        return f"Booking #{self.pk} — {self.category} ({self.get_status_display()})"

    def clean(self):
        if self.scheduled_for and self.scheduled_for < timezone.now() - timezone.timedelta(minutes=1):
            raise ValidationError({"scheduled_for": "Scheduled time cannot be in the past."})
        if self.customer_id and self.provider_id and self.customer_id == self.provider_id:
            raise ValidationError("Customer and provider must be different users.")

    def can_transition_to(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status, actor=None, note="", reason=""):
        """Apply a validated status transition and log it."""
        new_status = Booking.Status(new_status)
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot move booking from {self.get_status_display()} to "
                f"{new_status.label}."
            )
        previous = self.status
        self.status = new_status
        if note:
            self.provider_note = note
        if reason:
            self.cancel_reason = reason
        if new_status == Booking.Status.COMPLETED:
            self.completed_at = timezone.now()
        self.save()
        BookingStatusHistory.objects.create(
            booking=self,
            from_status=previous,
            to_status=new_status,
            changed_by=actor,
            note=note or reason,
        )
        return self

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_reviewable(self):
        return self.status == self.Status.PAID and not hasattr(self, "review")

    @property
    def platform_fee(self):
        from django.conf import settings as dj_settings

        pct = getattr(dj_settings, "PLATFORM_COMMISSION_PERCENT", 10)
        return round(self.quoted_price * pct / 100, 2)

    @property
    def provider_payout(self):
        return round(self.quoted_price - self.platform_fee, 2)


class BookingStatusHistory(models.Model):
    """Audit trail of every status change on a booking."""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="history"
    )
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Booking status history"

    def __str__(self):
        return f"#{self.booking_id}: {self.from_status} -> {self.to_status}"
