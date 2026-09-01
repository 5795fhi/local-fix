"""Delivery helpers for one-time passcodes.

In production these would hand off to an SMS/email provider. For this build we
log the code to the server console and surface it in the UI when DEBUG is on,
so the OTP flow is fully testable without external credentials.
"""
import logging

from django.conf import settings

logger = logging.getLogger("localfix.otp")


def send_otp(otp):
    """Dispatch an OTP to the user. Returns the code when DEBUG for previewing."""
    destination = otp.user.phone or otp.user.email
    logger.info("LocalFix OTP for %s [%s]: %s", destination, otp.purpose, otp.code)
    print(f"[LocalFix OTP] -> {destination} ({otp.purpose}): {otp.code}")
    return otp.code if settings.DEBUG else None
