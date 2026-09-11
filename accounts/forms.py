from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from services.models import ServiceCategory
from .models import ProviderProfile

User = get_user_model()

_TEXT = {"class": "input"}
_PASSWORD = {
    "class": "input password-input",
    "autocomplete": "current-password",
}


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=_TEXT))
    last_name = forms.CharField(
        max_length=150, required=False, widget=forms.TextInput(attrs=_TEXT)
    )
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs=_TEXT))
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={**_PASSWORD, "autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={**_PASSWORD, "autocomplete": "new-password"}
        ),
    )
    role = forms.ChoiceField(
        choices=[
            (User.Role.CUSTOMER, "I need to hire a professional"),
            (User.Role.PROVIDER, "I offer services"),
        ],
        widget=forms.RadioSelect,
        initial=User.Role.CUSTOMER,
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role"]
        widgets = {"email": forms.EmailInput(attrs=_TEXT)}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = True
        user.is_verified = False
        if commit:
            user.save()
        return user


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={**_TEXT, "autofocus": True, "autocomplete": "email"}
        ),
    )
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs=_PASSWORD)
    )


class OTPForm(forms.Form):
    code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": "input otp-input",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "placeholder": "000000",
            }
        ),
    )


class PasswordChangeForm(forms.Form):
    """Re-authenticate with the current password, then set a new one."""

    current_password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(attrs=_PASSWORD),
    )
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(
            attrs={**_PASSWORD, "autocomplete": "new-password"}
        ),
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={**_PASSWORD, "autocomplete": "new-password"}
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data["current_password"]
        if not self.user.check_password(current):
            raise forms.ValidationError("Your current password is incorrect.")
        return current

    def clean_new_password2(self):
        p1 = self.cleaned_data.get("new_password1")
        p2 = self.cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("New passwords do not match.")
        if p1:
            password_validation.validate_password(p1, self.user)
        return p2

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save(update_fields=["password"])
        return self.user


class EmailChangeForm(forms.Form):
    """Start an email change: verifies password, issues OTP to the new address."""

    new_email = forms.EmailField(
        label="New email address",
        widget=forms.EmailInput(attrs={**_TEXT, "autocomplete": "email"}),
    )
    current_password = forms.CharField(
        label="Confirm current password",
        widget=forms.PasswordInput(attrs=_PASSWORD),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        email = self.cleaned_data["new_email"].lower()
        if email == self.user.email:
            raise forms.ValidationError("That is already your current email.")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account already uses this email.")
        return email

    def clean_current_password(self):
        current = self.cleaned_data["current_password"]
        if not self.user.check_password(current):
            raise forms.ValidationError("Your current password is incorrect.")
        return current


class ProviderProfileForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = ProviderProfile
        fields = [
            "headline",
            "bio",
            "categories",
            "hourly_rate",
            "years_experience",
            "service_area",
            "is_available",
        ]
        widgets = {
            "headline": forms.TextInput(attrs=_TEXT),
            "bio": forms.Textarea(attrs={**_TEXT, "rows": 4}),
            "hourly_rate": forms.NumberInput(attrs=_TEXT),
            "years_experience": forms.NumberInput(attrs=_TEXT),
            "service_area": forms.TextInput(attrs=_TEXT),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "avatar"]
        widgets = {
            "first_name": forms.TextInput(attrs=_TEXT),
            "last_name": forms.TextInput(attrs=_TEXT),
            "phone": forms.TextInput(attrs=_TEXT),
        }
