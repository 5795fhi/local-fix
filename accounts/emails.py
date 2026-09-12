"""Transactional email for LocalFix.

Every message is rendered from a template pair in ``templates/emails/``:
``<name>.html`` (branded HTML) and ``<name>.txt`` (plain-text fallback).
All helpers are fire-safe — a failed send is logged and never breaks the
request that triggered it.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger("localfix.email")

User = get_user_model()

DEFAULT_FROM = getattr(
    settings, "DEFAULT_FROM_EMAIL", "LocalFix <no-reply@localfix.test>"
)
REPLY_TO = [settings.ADMINS[0][1]] if getattr(settings, "ADMINS", None) else None


def send_templated_email(name, to_email, context, subject=None):
    """Render ``emails/<name>.html`` + ``.txt`` and send them.

    Returns True when the message was handed to the email backend.
    """
    to_email = to_email or ""
    if not to_email:
        logger.warning("Templated email %s skipped: no recipient.", name)
        return False

    ctx = {"SITE_NAME": "LocalFix", "site_url": _site_url(), **(context or {})}
    subject = subject or render_to_string(
        f"emails/{name}_subject.txt", ctx
    ).strip()
    html_body = render_to_string(f"emails/{name}.html", ctx)
    text_body = render_to_string(f"emails/{name}.txt", ctx)

    message = EmailMultiAlternatives(
        subject, text_body, DEFAULT_FROM, [to_email],
        reply_to=REPLY_TO or [],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        sent = message.send()
    except Exception:  # pragma: no cover - backend misconfiguration
        logger.exception("Failed to send %s email to %s", name, to_email)
        return False
    if not sent:
        logger.warning("Email backend dropped %s to %s (recipient refused).", name, to_email)
    return bool(sent)


def _site_url():
    request_base = getattr(settings, "SITE_BASE_URL", "")
    return (request_base or "http://127.0.0.1:8000").rstrip("/")


def _full(url_path):
    return f"{_site_url()}{url_path}" if url_path.startswith("/") else url_path


# --- Identity & security ------------------------------------------------------


def send_otp_email(otp):
    """Deliver a one-time passcode for verification / login / reset flows."""
    purpose = otp.get_purpose_display() if otp.purpose != "verify" else "account verification"
    return send_templated_email(
        "otp",
        otp.user.email,
        {
            "user": otp.user,
            "code": otp.code,
            "purpose": purpose,
            "ttl_minutes": max(1, getattr(settings, "OTP_TTL_SECONDS", 300) // 60),
        },
        subject=f"Your LocalFix code: {otp.code}",
    )


def send_welcome_email(user):
    """One-time welcome after successful account verification."""
    if user.is_provider:
        cta_url, cta_label = _full("/accounts/profile/"), "Complete your pro profile"
        blurb = (
            "Add your skills, service area and hourly rate so customers can find "
            "and book you. An admin will approve your profile shortly after."
        )
    else:
        cta_url, cta_label = _full("/services/providers/"), "Browse professionals"
        blurb = (
            "Browse verified local pros, compare rates and reviews, and book a "
            "time that suits you. You only pay once the work is done."
        )
    return send_templated_email(
        "welcome",
        user.email,
        {"user": user, "cta_url": cta_url, "cta_label": cta_label, "blurb": blurb},
        subject="Welcome to LocalFix — let's get you set up",
    )


def send_password_changed_email(user):
    return send_templated_email(
        "password_changed",
        user.email,
        {"user": user, "support_url": _full("/contact/")},
        subject="Your LocalFix password was changed",
    )


def send_email_change_confirm_email(otp):
    """OTP sent to the *new* address to confirm an email change."""
    return send_templated_email(
        "email_change_confirm",
        otp.sent_to,
        {
            "user": otp.user,
            "code": otp.code,
            "ttl_minutes": max(1, getattr(settings, "OTP_TTL_SECONDS", 300) // 60),
        },
        subject=f"Confirm your new LocalFix email — code {otp.code}",
    )


def send_email_changed_notice_email(user, old_email):
    return send_templated_email(
        "email_changed_notice",
        old_email,
        {"user": user, "new_email": user.email, "support_url": _full("/contact/")},
        subject="Your LocalFix email address was changed",
    )


# --- Provider approval --------------------------------------------------------


def send_provider_approved_email(user):
    """Tell a professional their profile was approved; they're now bookable."""
    return send_templated_email(
        "provider_approved",
        user.email,
        {
            "user": user,
            "directory_url": _full("/services/providers/"),
            "dashboard_url": _full("/dashboard/"),
        },
        subject="You're approved — customers can now book you on LocalFix",
    )


def send_negotiation_email(booking, offer_by, note="", accepted=False, declined_old=None):
    """Tell the other party about a price offer / counter / acceptance."""
    customer, provider = booking.customer, booking.provider
    recipient = provider if offer_by.pk == customer.pk else customer
    amount = f"₹{booking.quoted_price:,.0f}"

    if accepted:
        heading = f"Offer accepted — {amount} agreed"
        body = (
            f"{offer_by.display_name} accepted {amount} as the final price for "
            f"booking #{booking.pk}. The commission and payout are now calculated "
            f"from this agreed amount."
        )
    elif declined_old is not None:
        heading = f"Counter-offer: {amount}"
        body = (
            f"{offer_by.display_name} declined ₹{declined_old:,.0f} and countered "
            f"{amount} for booking #{booking.pk}."
            + (f" Note: {note}" if note else "")
        )
    else:
        label = "Customer" if offer_by.pk == customer.pk else "Professional"
        heading = f"New price offer: {amount}"
        body = (
            f"{offer_by.display_name} ({label}) proposed {amount} for booking "
            f"#{booking.pk}."
            + (f" Note: {note}" if note else "")
        )

    return send_templated_email(
        "negotiation",
        recipient.email,
        {
            "user": recipient,
            "other": offer_by,
            "booking": booking,
            "heading": heading,
            "body": body,
            "amount": amount,
            "cta_url": _full(f"/bookings/{booking.pk}/"),
            "status_label": booking.get_status_display(),
        },
        subject=f"{heading} · LocalFix booking #{booking.pk}",
    )


# --- Booking lifecycle --------------------------------------------------------


def send_booking_email(kind, booking, actor=None, extra_note=""):
    """Notify the *other* party about a booking status change.

    kind: requested | accepted | started | completed | paid | rejected | cancelled
    actor: the user whose action triggered the change (used to pick recipient).
    """
    status_urls = {
        "requested": "New booking request",
        "accepted": "Your booking was accepted",
        "started": "Work has started",
        "completed": "Work completed — ready for payment",
        "paid": "Payment received",
        "rejected": "Your booking request was declined",
        "cancelled": "Booking cancelled",
    }
    subject = status_urls.get(kind, "Booking update")
    customer = booking.customer
    provider = booking.provider

    if kind == "requested":
        recipient, other = provider, customer
        heading = "You have a new booking request"
        body = (
            f"{customer.display_name} requested {booking.category} on "
            f"{booking.scheduled_for:%a, %d %b %Y at %H:%M}. Review the request "
            f"and send your quote."
        )
    elif kind == "accepted":
        recipient, other = customer, provider
        heading = "Your booking was accepted"
        body = (
            f"{provider.display_name} accepted your request and quoted "
            f"{booking.quoted_price}. The job is scheduled for "
            f"{booking.scheduled_for:%a, %d %b %Y at %H:%M}."
        )
    elif kind == "started":
        recipient, other = customer, provider
        heading = "Work has started"
        body = (
            f"{provider.display_name} started working on booking #{booking.pk}. "
            f"You can track progress from your dashboard."
        )
    elif kind == "completed":
        recipient, other = customer, provider
        heading = "Work completed"
        body = (
            f"{provider.display_name} marked booking #{booking.pk} complete. "
            f"Amount due: {booking.quoted_price}. Pay securely to close it out."
        )
    elif kind == "paid":
        recipient, other = provider, customer
        heading = "Payment received"
        body = (
            f"{customer.display_name} paid {booking.quoted_price} for booking "
            f"#{booking.pk}. Your payout of {booking.provider_payout} will be "
            f"settled per the platform schedule."
        )
    elif kind == "rejected":
        recipient, other = customer, provider
        heading = "Request declined"
        body = (
            f"{provider.display_name} declined your request for "
            f"{booking.category}.{(' Note: ' + extra_note) if extra_note else ''}"
        )
    else:  # cancelled
        recipient = booking.customer if actor and actor.pk == provider.pk else provider
        other = provider if recipient is customer else customer
        heading = "Booking cancelled"
        body = (
            f"{other.display_name} cancelled booking #{booking.pk}."
            f"{(' Reason: ' + extra_note) if extra_note else ''}"
        )

    return send_templated_email(
        "booking_status",
        recipient.email,
        {
            "user": recipient,
            "other": other,
            "booking": booking,
            "heading": heading,
            "body": body,
            "cta_url": _full(f"/bookings/{booking.pk}/"),
            "status_label": booking.get_status_display(),
        },
        subject=f"{subject} · LocalFix booking #{booking.pk}",
    )
