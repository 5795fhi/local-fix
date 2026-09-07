import secrets

from django.conf import settings
from django.db import models


class Payment(models.Model):
    """Records payment for a completed booking.

    This is a mock payment boundary: it models the states a real gateway
    integration (Stripe, etc.) would drive, without moving real money.
    """

    class Method(models.TextChoices):
        CARD = "card", "Card"
        WALLET = "wallet", "Wallet"
        CASH = "cash", "Cash on completion"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.CASCADE, related_name="payment"
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    provider_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CARD)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    reference = models.CharField(max_length=40, unique=True, blank=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.reference} for booking #{self.booking_id}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = "LF-" + secrets.token_hex(8).upper()
        super().save(*args, **kwargs)
