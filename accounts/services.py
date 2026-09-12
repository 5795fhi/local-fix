"""Delivery for one-time passcodes.

Codes are emailed through the transactional layer in ``accounts.emails``
(real SMTP — see README "Setting up real email"). The code is never shown
in the UI; when the console email backend is active (local dev without
SMTP configured), the code still appears in the server console.
"""
import logging

from django.conf import settings

from .emails import send_otp_email

logger = logging.getLogger("localfix.otp")


def send_otp(otp):
    """Email an OTP to its user; returns True when the backend accepted it."""
    sent = send_otp_email(otp)
    if sent:
        logger.info("OTP email for %s (%s) delivered.", otp.user.email, otp.purpose)
    else:
        logger.warning("OTP email for %s may not have been delivered.", otp.user.email)
        if "console" in settings.EMAIL_BACKEND:
            # Dev fallback (no SMTP configured): make the code reachable.
            logger.info("LocalFix OTP for %s [%s]: %s", otp.user.email, otp.purpose, otp.code)
    return sent
