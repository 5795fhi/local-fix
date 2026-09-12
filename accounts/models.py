import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractUser):
    """Custom user identified by email, carrying a platform role."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        PROVIDER = "provider", "Service Provider"
        ADMIN = "admin", "Administrator"

    username = None
    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_verified = models.BooleanField(
        default=False, help_text="Whether the account has passed OTP verification."
    )
    welcome_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the one-time welcome email has been delivered.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_provider(self):
        return self.role == self.Role.PROVIDER

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def display_name(self):
        return self.get_full_name() or self.email.split("@")[0]

    @property
    def avatar_variant(self):
        """Pick one of the built-in avatar palettes without storing a file."""
        return ((self.pk or 0) % 6) + 1

    def mark_welcome_email_sent(self):
        from django.utils import timezone

        self.welcome_email_sent_at = timezone.now()
        self.save(update_fields=["welcome_email_sent_at"])


class ProviderProfile(models.Model):
    """Extended profile and availability data for service providers."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="provider_profile",
    )
    headline = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    categories = models.ManyToManyField(
        "services.ServiceCategory", related_name="providers", blank=True
    )
    hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Base hourly rate in local currency.",
    )
    years_experience = models.PositiveIntegerField(default=0)
    service_area = models.CharField(max_length=120, blank=True)
    is_available = models.BooleanField(default=True)
    is_approved = models.BooleanField(
        default=False, help_text="Approved by an administrator to accept bookings."
    )
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Provider: {self.user.display_name}"

    def recalculate_rating(self):
        from reviews.models import Review

        agg = Review.objects.filter(provider=self.user).aggregate(
            avg=models.Avg("rating"), count=models.Count("id")
        )
        self.rating_avg = round(agg["avg"] or 0, 2)
        self.rating_count = agg["count"] or 0
        self.save(update_fields=["rating_avg", "rating_count"])


class OTP(models.Model):
    """One-time passcode for verifying an account or resetting a password."""

    class Purpose(models.TextChoices):
        VERIFY = "verify", "Account verification"
        RESET = "reset", "Password reset"
        LOGIN = "login", "Login confirmation"
        EMAIL_CHANGE = "email_change", "Email change"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    code = models.CharField(max_length=10)
    purpose = models.CharField(
        max_length=15, choices=Purpose.choices, default=Purpose.VERIFY
    )
    sent_to = models.EmailField(
        blank=True,
        help_text="Delivery address when the OTP was issued (e.g. a new email pending confirmation).",
    )
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP {self.code} for {self.user.email} ({self.purpose})"

    @classmethod
    def issue(cls, user, purpose=Purpose.VERIFY):
        """Invalidate previous codes and create a fresh one."""
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(
            is_used=True
        )
        length = getattr(settings, "OTP_LENGTH", 6)
        code = "".join(secrets.choice("0123456789") for _ in range(length))
        return cls.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=timezone.now()
            + timedelta(seconds=getattr(settings, "OTP_TTL_SECONDS", 300)),
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def verify(self, code):
        """Return True if the provided code is valid; records the attempt."""
        max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
        if self.is_used or self.is_expired or self.attempts >= max_attempts:
            return False
        self.attempts += 1
        if secrets.compare_digest(self.code, code.strip()):
            self.is_used = True
            self.save(update_fields=["attempts", "is_used"])
            return True
        self.save(update_fields=["attempts"])
        return False
