from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*roles):
    """Allow access only to authenticated users whose role is in `roles`."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.is_superuser or request.user.role in roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have access to this area.")

        return _wrapped

    return decorator


def verified_required(view_func):
    """Require the account to have completed OTP verification."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.is_verified and not request.user.is_superuser:
            messages.warning(request, "Please verify your account to continue.")
            return redirect("accounts:verify")
        return view_func(request, *args, **kwargs)

    return _wrapped
