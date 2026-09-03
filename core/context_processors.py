from django.conf import settings


def site_context(request):
    """Expose shared values to every template."""
    return {
        "SITE_NAME": "LocalFix",
        "SITE_TAGLINE": "Trusted local pros, booked in minutes.",
        "unread_notifications": getattr(request, "unread_notifications", 0),
        "commission_pct": getattr(settings, "PLATFORM_COMMISSION_PERCENT", 10),
    }
