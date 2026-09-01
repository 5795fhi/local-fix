from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from services.models import ServiceCategory
from .models import ProviderProfile

User = get_user_model()

_TEXT = {"class": "input"}


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs=_TEXT))
    last_name = forms.CharField(
        max_length=150, required=False, widget=forms.TextInput(attrs=_TEXT)
    )
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs=_TEXT))
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs=_TEXT)
    )
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput(attrs=_TEXT)
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
        widget=forms.EmailInput(attrs={**_TEXT, "autofocus": True}),
    )
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs=_TEXT)
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
