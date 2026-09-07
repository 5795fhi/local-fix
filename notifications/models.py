from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification delivered to a single user."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=140)
    body = models.CharField(max_length=280, blank=True)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.recipient.email}"

    @classmethod
    def notify(cls, recipient, title, body="", url=""):
        return cls.objects.create(
            recipient=recipient, title=title, body=body, url=url
        )
