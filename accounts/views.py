from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from notifications.models import Notification
from .decorators import verified_required
from .forms import (
    EmailLoginForm,
    OTPForm,
    ProfileForm,
    ProviderProfileForm,
    RegisterForm,
)
from .models import OTP
from .services import send_otp

User = get_user_model()


def register(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            otp = OTP.issue(user, OTP.Purpose.VERIFY)
            preview = send_otp(otp)
            request.session["pending_user_id"] = user.id
            if preview:
                messages.info(request, f"Your verification code is {preview} (demo mode).")
            messages.success(
                request, "Account created. Enter the code we sent to verify."
            )
            return redirect("accounts:verify")
    else:
        form = RegisterForm(initial={"role": request.GET.get("role", "customer")})
    return render(request, "accounts/register.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_verified and not user.is_superuser:
            otp = OTP.issue(user, OTP.Purpose.VERIFY)
            preview = send_otp(otp)
            self.request.session["pending_user_id"] = user.id
            if preview:
                messages.info(
                    self.request, f"Your verification code is {preview} (demo mode)."
                )
            messages.warning(self.request, "Verify your account to finish signing in.")
            return redirect("accounts:verify")
        return super().form_valid(form)


def verify(request):
    user_id = request.session.get("pending_user_id")
    if not user_id:
        messages.error(request, "No verification in progress. Please log in.")
        return redirect("accounts:login")
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect("accounts:login")

    if request.method == "POST":
        form = OTPForm(request.POST)
        if form.is_valid():
            otp = (
                OTP.objects.filter(
                    user=user, purpose=OTP.Purpose.VERIFY, is_used=False
                )
                .order_by("-created_at")
                .first()
            )
            if otp and otp.verify(form.cleaned_data["code"]):
                user.is_verified = True
                user.save(update_fields=["is_verified"])
                request.session.pop("pending_user_id", None)
                login(request, user)
                Notification.notify(
                    user,
                    "Welcome to LocalFix!",
                    "Your account is verified. Start exploring services.",
                    url=reverse("core:dashboard"),
                )
                messages.success(request, "Your account is verified.")
                return redirect("core:dashboard")
            messages.error(request, "Invalid or expired code. Try again.")
    else:
        form = OTPForm()
    return render(request, "accounts/verify.html", {"form": form, "target": user.email})


def resend_otp(request):
    user_id = request.session.get("pending_user_id")
    if not user_id:
        return redirect("accounts:login")
    user = User.objects.filter(pk=user_id).first()
    if user:
        otp = OTP.issue(user, OTP.Purpose.VERIFY)
        preview = send_otp(otp)
        if preview:
            messages.info(request, f"Your new code is {preview} (demo mode).")
        messages.success(request, "A new code has been sent.")
    return redirect("accounts:verify")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("core:home")


@login_required
def profile(request):
    if request.method == "POST" and "profile" in request.POST:
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    provider_form = None
    if request.user.is_provider:
        prof = request.user.provider_profile
        if request.method == "POST" and "provider" in request.POST:
            provider_form = ProviderProfileForm(request.POST, instance=prof)
            if provider_form.is_valid():
                provider_form.save()
                messages.success(request, "Provider details updated.")
                return redirect("accounts:profile")
        else:
            provider_form = ProviderProfileForm(instance=prof)

    return render(
        request,
        "accounts/profile.html",
        {"form": form, "provider_form": provider_form},
    )
