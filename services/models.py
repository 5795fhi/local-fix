from django.db import models
from django.utils.text import slugify


class ServiceCategory(models.Model):
    """A category of work customers can book (plumbing, electrical, etc.)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=40, blank=True,
        help_text="Lucide/emoji icon name rendered on the category card.",
    )
    base_price = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Indicative starting price shown to customers.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Service categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def provider_count(self):
        return self.providers.filter(is_approved=True, is_available=True).count()

    @property
    def icon_emoji(self):
        """Map the seeded Lucide-style icon name to an emoji for the UI."""
        return {
            "wrench": "🔧", "zap": "⚡", "hammer": "🪚", "sparkles": "🧹",
            "paint-roller": "🎨", "wind": "🌀", "plug": "🔌", "leaf": "🌿",
            "snowflake": "❄️", "settings": "🛠️",
        }.get(self.icon, "🛠️")
