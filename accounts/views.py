from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from notifications.models import Notification
from .decorators import verified_required
from .emails import (
    send_email_changed_notice_email,
    send_password_changed_email,
    send_welcome_email,
)
from .forms import (
    EmailChangeForm,
    EmailLoginForm,
    OTPForm,
    PasswordChangeForm,
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
                request, "Account created. We emailed you a verification code."
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
                if not user.welcome_email_sent_at:
                    send_welcome_email(user)
                    user.mark_welcome_email_sent()
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
        messages.success(request, "A new code has been emailed to you.")
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

    password_form = PasswordChangeForm(user=request.user)
    email_form = EmailChangeForm(user=request.user)

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "provider_form": provider_form,
            "password_form": password_form,
            "email_form": email_form,
        },
    )


@login_required
@verified_required
def change_password(request):
    if request.method != "POST":
        return redirect("accounts:profile")
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # keep the user signed in
        send_password_changed_email(user)
        Notification.notify(
            user,
            "Password changed",
            "Your LocalFix password was updated. Contact support if this wasn't you.",
            url=reverse("accounts:profile"),
        )
        messages.success(request, "Password updated. A confirmation email has been sent.")
        return redirect("accounts:profile")
    messages.error(request, "Please fix the errors below.")
    return render(
        request,
        "accounts/profile.html",
        {
            "form": ProfileForm(instance=request.user),
            "provider_form": (
                ProviderProfileForm(instance=request.user.provider_profile)
                if request.user.is_provider
                else None
            ),
            "password_form": form,
            "email_form": EmailChangeForm(user=request.user),
            "open_section": "password",
        },
    )


@login_required
@verified_required
def change_email(request):
    """Step 1: password check -> issue OTP bound to the NEW address."""
    if request.method != "POST":
        return redirect("accounts:profile")
    form = EmailChangeForm(request.user, request.POST)
    if form.is_valid():
        from .emails import send_email_change_confirm_email

        new_email = form.cleaned_data["new_email"]
        otp = OTP.issue(request.user, OTP.Purpose.EMAIL_CHANGE)
        otp.sent_to = new_email
        otp.save(update_fields=["sent_to"])
        send_email_change_confirm_email(otp)
        request.session["email_change_new"] = new_email
        messages.info(
            request,
            f"We sent a confirmation code to {new_email}. Enter it to finish.",
        )
        return redirect("accounts:email_change_verify")
    messages.error(request, "Please fix the errors below.")
    return render(
        request,
        "accounts/profile.html",
        {
            "form": ProfileForm(instance=request.user),
            "provider_form": (
                ProviderProfileForm(instance=request.user.provider_profile)
                if request.user.is_provider
                else None
            ),
            "password_form": PasswordChangeForm(user=request.user),
            "email_form": form,
            "open_section": "email",
        },
    )


@login_required
@verified_required
def email_change_verify(request):
    """Step 2: confirm the OTP sent to the new address, then switch."""
    new_email = request.session.get("email_change_new")
    if not new_email:
        messages.error(request, "No email change in progress.")
        return redirect("accounts:profile")

    if request.method == "POST":
        form = OTPForm(request.POST)
        if form.is_valid():
            otp = (
                OTP.objects.filter(
                    user=request.user, purpose=OTP.Purpose.EMAIL_CHANGE, is_used=False
                )
                .order_by("-created_at")
                .first()
            )
            if otp and otp.verify(form.cleaned_data["code"]):
                old_email = request.user.email
                request.user.email = new_email
                request.user.save(update_fields=["email"])
                request.session.pop("email_change_new", None)
                send_email_changed_notice_email(request.user, old_email)
                Notification.notify(
                    request.user,
                    "Email updated",
                    f"Your sign-in email is now {new_email}.",
                    url=reverse("accounts:profile"),
                )
                messages.success(request, f"Your email is now {new_email}.")
                return redirect("accounts:profile")
            messages.error(request, "Invalid or expired code. Try again.")
    else:
        form = OTPForm()
    return render(
        request,
        "accounts/email_change_verify.html",
        {"form": form, "target": new_email},
    )
