"""Match a customer's request to approved LocalFix professionals."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from django.db.models import Prefetch
from django.utils import timezone

from accounts.models import ProviderProfile
from services.models import ServiceCategory

_CATEGORY_HINTS = {
    "leak": "plumbing",
    "pipe": "plumbing",
    "tap": "plumbing",
    "faucet": "plumbing",
    "drain": "plumbing",
    "toilet": "plumbing",
    "plumber": "plumbing",
    "plumbing": "plumbing",
    "water heater": "plumbing",
    "light": "electrical",
    "wiring": "electrical",
    "socket": "electrical",
    "outlet": "electrical",
    "power": "electrical",
    "switch": "electrical",
    "fuse": "electrical",
    "electrician": "electrical",
    "electrical": "electrical",
    "wood": "carpentry",
    "door": "carpentry",
    "furniture": "carpentry",
    "cabinet": "carpentry",
    "shelf": "carpentry",
    "carpenter": "carpentry",
    "carpentry": "carpentry",
    "clean": "cleaning",
    "dust": "cleaning",
    "tidy": "cleaning",
    "housekeep": "cleaning",
    "cleaner": "cleaning",
    "cleaning": "cleaning",
    "paint": "painting",
    "painter": "painting",
    "painting": "painting",
    "wall": "painting",
    "ac": "hvac",
    "hvac": "hvac",
    "heating": "hvac",
    "cooling": "hvac",
    "air condition": "hvac",
    "ventilation": "hvac",
    "washer": "appliance repair",
    "fridge": "appliance repair",
    "oven": "appliance repair",
    "dishwasher": "appliance repair",
    "appliance": "appliance repair",
    "handyman": "home maintenance",
    "odd job": "home maintenance",
    "maintenance": "home maintenance",
    "repair": "home maintenance",
    "fix": "home maintenance",
}

_INTENT = (
    "need", "book", "fix", "repair", "leak", "broken", "install",
    "plumber", "electrician", "carpenter", "cleaner", "painter",
    "professional", "pro", "service", "help with", "coming over",
)


def infer_category(text):
    lowered = (text or "").lower()
    for keyword, slug_or_name in _CATEGORY_HINTS.items():
        if keyword in lowered:
            category = ServiceCategory.objects.filter(
                is_active=True, slug=slug_or_name
            ).first()
            if category:
                return category
            category = ServiceCategory.objects.filter(
                is_active=True, name__iexact=slug_or_name
            ).first()
            if category:
                return category
    return None


def should_suggest_providers(text):
    lowered = (text or "").lower()
    if infer_category(lowered):
        return True
    return any(word in lowered for word in _INTENT)


def extract_datetime(text):
    """Best-effort parse of a future date/time mentioned in chat."""
    if not text:
        return None
    now = timezone.localtime()
    lowered = text.lower()

    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})[ t](\d{1,2}:\d{2})\b", text)
    if iso:
        try:
            naive = datetime.strptime(f"{iso.group(1)} {iso.group(2)}", "%Y-%m-%d %H:%M")
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            pass

    local = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        lowered,
    )
    if local:
        day, month, year = int(local.group(1)), int(local.group(2)), int(local.group(3))
        hour = int(local.group(4))
        minute = int(local.group(5) or 0)
        meridiem = local.group(6)
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        try:
            naive = datetime(year, month, day, hour, minute)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except ValueError:
            pass

    time_m = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lowered)
    if time_m:
        hour = int(time_m.group(1))
        minute = int(time_m.group(2) or 0)
        meridiem = time_m.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        day = now
        if "tomorrow" in lowered:
            day = now + timedelta(days=1)
        candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            return candidate

    return None


def serialize_provider(profile, category=None):
    cats = list(profile.categories.all())
    chosen = category if category and any(c.pk == category.pk for c in cats) else None
    if chosen is None and cats:
        chosen = cats[0]
    return {
        "id": profile.pk,
        "name": profile.user.display_name,
        "avatar": profile.user.avatar.url if profile.user.avatar else "",
        "headline": profile.headline or "Local professional",
        "rating": f"{profile.rating_avg:.1f}",
        "reviews": profile.rating_count,
        "rate": f"{profile.hourly_rate:,.0f}",
        "area": profile.service_area or "Local",
        "years": profile.years_experience,
        "categories": [c.name for c in cats],
        "category_id": chosen.pk if chosen else None,
        "category_name": chosen.name if chosen else "",
    }


def suggest_providers(user, text, limit=4):
    category = infer_category(text)
    qs = (
        ProviderProfile.objects.filter(is_approved=True, is_available=True)
        .exclude(user=user)
        .select_related("user")
        .prefetch_related(Prefetch("categories", queryset=ServiceCategory.objects.all()))
        .order_by("-rating_avg", "-rating_count", "hourly_rate")
        .distinct()
    )
    matched = qs.filter(categories=category) if category else qs
    profiles = list(matched[:limit])
    if len(profiles) < limit:
        seen = {p.pk for p in profiles}
        filler = qs.exclude(pk__in=seen)
        extras = []
        if category:
            extras.extend(
                qs.filter(categories__name__iexact="Home Maintenance").exclude(pk__in=seen)
            )
        extras.extend(filler)
        for extra in extras:
            if extra.pk in seen:
                continue
            profiles.append(extra)
            seen.add(extra.pk)
            if len(profiles) >= limit:
                break
    return category, [serialize_provider(p, category) for p in profiles]


def format_provider_context(category, suggestions):
    if not suggestions:
        return ""
    cat_label = category.name if category else "your request"
    lines = [
        f"Matching LocalFix professionals for {cat_label}. "
        "Recommend only these people (do not invent names or prices). "
        "Ask the user to pick one, then confirm a date, time, and job address "
        "so a booking request can be placed:",
    ]
    for i, pro in enumerate(suggestions, start=1):
        lines.append(
            f"{i}. {pro['name']} — {pro['headline']} — "
            f"★{pro['rating']} ({pro['reviews']} reviews) — "
            f"{pro['rate']}/hr — {pro['area']} — {pro['years']} yrs"
        )
    return "\n".join(lines)
