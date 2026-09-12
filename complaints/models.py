from django.conf import settings
from django.db import models


class Complaint(models.Model):
    """A dispute raised by a customer or provider, triaged by admins."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In review"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="complaints_raised",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
    )
    # Snapshot of the professional being reported, kept even if the booking or
    # provider account is later deleted.
    reported_professional_name = models.CharField(max_length=120, blank=True)
    reported_professional_email = models.EmailField(blank=True)
    reported_professional_phone = models.CharField(max_length=20, blank=True)
    reported_service = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=140)
    description = models.TextField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.OPEN
    )
    resolution = models.TextField(blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_handled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Complaint #{self.pk}: {self.subject}"
