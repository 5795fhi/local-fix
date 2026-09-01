from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProviderProfile, User


@receiver(post_save, sender=User)
def ensure_provider_profile(sender, instance, created, **kwargs):
    """Give every provider account a profile record automatically."""
    if instance.role == User.Role.PROVIDER:
        ProviderProfile.objects.get_or_create(user=instance)
