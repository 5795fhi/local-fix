"""Delivery helpers for one-time passcodes.

Codes are emailed through the transactional layer in ``accounts.emails``. When
DEBUG is on, the code is also logged to the server console (and surfaced in the
UI banner) so the flow stays fully testable without real mail credentials.
"""
import logging

from django.conf import settings

from .emails import send_otp_email

logger = logging.getLogger("localfix.otp")


def send_otp(otp):
    """Email an OTP to the user; returns the code when DEBUG for previewing."""
    sent = send_otp_email(otp)
    if settings.DEBUG:
        destination = otp.user.email
        logger.info("LocalFix OTP for %s [%s]: %s", destination, otp.purpose, otp.code)
        print(f"[LocalFix OTP] -> {destination} ({otp.purpose}): {otp.code}")
        return otp.code
    if not sent:
        logger.warning("OTP email for %s may not have been delivered.", otp.user.email)
    return None
