import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.emails import send_provider_approved_email
from accounts.models import ProviderProfile
from bookings.models import Booking
from notifications.models import Notification
from complaints.models import Complaint
from payments.models import Payment
from reviews.models import Review
from services.models import ServiceCategory

User = get_user_model()


def home(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    context = {
        "categories": ServiceCategory.objects.filter(is_active=True)[:8],
        "top_providers": ProviderProfile.objects.filter(is_approved=True)
        .select_related("user")
        .order_by("-rating_avg", "-rating_count")[:4],
        "provider_count": ProviderProfile.objects.filter(is_approved=True).count(),
        "booking_count": Booking.objects.filter(
            status__in=[Booking.Status.COMPLETED, Booking.Status.PAID]
        ).count(),
        "category_count": ServiceCategory.objects.filter(is_active=True).count(),
    }
    return render(request, "core/home.html", context)


@login_required
def dashboard(request):
    user = request.user
    if user.is_platform_admin:
        return _admin_dashboard(request)
    if user.is_provider:
        return _provider_dashboard(request)
    return _customer_dashboard(request)


def _customer_dashboard(request):
    user = request.user
    bookings = user.bookings_made.select_related("provider", "category")
    context = {
        "active_bookings": bookings.filter(status__in=Booking.OPEN_STATUSES),
        "awaiting_payment": bookings.filter(status=Booking.Status.COMPLETED),
        "recent_bookings": bookings[:5],
        "total_spent": Payment.objects.filter(
            payer=user, status=Payment.Status.SUCCEEDED
        ).aggregate(t=Sum("amount"))["t"]
        or 0,
        "review_count": Review.objects.filter(customer=user).count(),
        "categories": ServiceCategory.objects.filter(is_active=True)[:6],
    }
    return render(request, "core/dashboard_customer.html", context)


def _provider_dashboard(request):
    user = request.user
    profile = getattr(user, "provider_profile", None)
    bookings = user.bookings_received.select_related("customer", "category")
    context = {
        "profile": profile,
        "pending_requests": bookings.filter(status=Booking.Status.REQUESTED),
        "active_jobs": bookings.filter(
            status__in=[Booking.Status.ACCEPTED, Booking.Status.IN_PROGRESS]
        ),
        "recent_bookings": bookings[:5],
        "earnings": Payment.objects.filter(
            booking__provider=user, status=Payment.Status.SUCCEEDED
        ).aggregate(t=Sum("provider_payout"))["t"]
        or 0,
        "completed_count": bookings.filter(
            status__in=[Booking.Status.COMPLETED, Booking.Status.PAID]
        ).count(),
    }
    return render(request, "core/dashboard_provider.html", context)


def _admin_dashboard(request):
    status_breakdown = list(
        Booking.objects.values("status").annotate(n=Count("id"))
    )
    max_status_count = max((row["n"] for row in status_breakdown), default=0) or 1
    context = {
        "user_count": User.objects.count(),
        "customer_count": User.objects.filter(role=User.Role.CUSTOMER).count(),
        "provider_count": User.objects.filter(role=User.Role.PROVIDER).count(),
        "pending_providers": ProviderProfile.objects.filter(is_approved=False)
        .select_related("user"),
        "booking_count": Booking.objects.count(),
        "open_complaints": Complaint.objects.filter(
            status__in=[Complaint.Status.OPEN, Complaint.Status.IN_REVIEW]
        ).count(),
        "revenue": Payment.objects.filter(status=Payment.Status.SUCCEEDED).aggregate(
            t=Sum("platform_fee")
        )["t"]
        or 0,
        "status_breakdown": status_breakdown,
        "max_status_count": max_status_count,
        "recent_bookings": Booking.objects.select_related(
            "customer", "provider", "category"
        )[:8],
    }
    return render(request, "core/dashboard_admin.html", context)


@login_required
@require_POST
def approve_provider(request, pk):
    if not request.user.is_platform_admin:
        return redirect("core:dashboard")
    profile = get_object_or_404(ProviderProfile.objects.select_related("user"), pk=pk)
    if not profile.is_approved:
        profile.is_approved = True
        profile.save(update_fields=["is_approved"])
        Notification.notify(
            profile.user,
            "Profile approved 🎉",
            "You're now a verified LocalFix professional — customers can book you.",
            url=reverse("core:dashboard"),
        )
        send_provider_approved_email(profile.user)
    return redirect("core:dashboard")


# --- Static pages -------------------------------------------------------------


def about(request):
    context = {
        "provider_count": ProviderProfile.objects.filter(is_approved=True).count(),
        "booking_count": Booking.objects.filter(
            status__in=[Booking.Status.COMPLETED, Booking.Status.PAID]
        ).count(),
        "category_count": ServiceCategory.objects.filter(is_active=True).count(),
    }
    return render(request, "core/about.html", context)


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()
        if not name or not email or not message:
            messages.error(request, "Please fill in every field.")
        elif "@" not in email:
            messages.error(request, "Please enter a valid email address.")
        else:
            sent = send_mail(
                f"LocalFix contact form — {name}",
                f"From: {name} <{email}>\n\n{message}",
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=True,
            )
            if sent:
                messages.success(
                    request, "Thanks! Your message has been sent — we'll reply soon."
                )
            else:
                messages.info(
                    request,
                    "Thanks! Your message was recorded, but email delivery is not "
                    "configured yet — we'll still follow up.",
                )
            return redirect("core:contact")
    return render(request, "core/contact.html")


def terms(request):
    return render(request, "core/terms.html")


def privacy(request):
    return render(request, "core/privacy.html")


def version_info(request):
    """Tiny deployment probe: reports which git revision is actually running.

    Deploy platforms occasionally rebuild a stale commit (cache, old redeploy
    button, monorepo root misconfig). Hitting /versionz/ after a deploy proves
    which commit the live build came from.
    """
    import subprocess

    def _git(*args):
        try:
            return subprocess.run(
                ["git", *args], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except Exception:
            return ""

    commit = (
        os.environ.get("VERCEL_GIT_COMMIT_SHA")
        or os.environ.get("RENDER_GIT_COMMIT")
        or _git("rev-parse", "--short", "HEAD")
        or "unknown"
    )
    return JsonResponse(
        {
            "app": "localfix",
            "commit": commit[:12],
            "debug": settings.DEBUG,
        }
    )


# --- Error handlers (referenced by handler404/handler500 in localfix.urls) ----


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
