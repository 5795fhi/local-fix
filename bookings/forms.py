from django import forms
from django.utils import timezone

from .models import Booking

_TEXT = {"class": "input"}


class BookingForm(forms.ModelForm):
    scheduled_for = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={**_TEXT, "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    class Meta:
        model = Booking
        fields = ["category", "description", "address", "scheduled_for"]
        widgets = {
            "description": forms.Textarea(attrs={**_TEXT, "rows": 4}),
            "address": forms.TextInput(attrs=_TEXT),
            "category": forms.Select(attrs=_TEXT),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        soon = (timezone.now() + timezone.timedelta(minutes=30)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        far = (timezone.now() + timezone.timedelta(days=60)).strftime("%Y-%m-%dT%H:%M")
        w = self.fields["scheduled_for"].widget.attrs
        w["min"] = soon
        w["max"] = far

    def clean_scheduled_for(self):
        value = self.cleaned_data["scheduled_for"]
        if value < timezone.now():
            raise forms.ValidationError("Please choose a future date and time.")
        return value


class OfferForm(forms.Form):
    """The customer's first price proposal after the professional's quote."""

    quoted_price = forms.DecimalField(
        min_value=1, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={**_TEXT, "step": "0.01", "inputmode": "decimal"}),
    )
    note = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={**_TEXT, "placeholder": "Optional note (why this price?)"}),
    )


class QuoteForm(forms.Form):
    """Provider sets a price when accepting a booking."""

    quoted_price = forms.DecimalField(
        min_value=0, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={**_TEXT, "step": "0.01"}),
    )
    provider_note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={**_TEXT, "rows": 3})
    )


class DeclineOfferForm(forms.Form):
    """Counter with a different price instead of accepting an offer."""

    counter_price = forms.DecimalField(
        min_value=1, max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={**_TEXT, "step": "0.01", "inputmode": "decimal"}),
    )
    note = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={**_TEXT, "placeholder": "Optional note"}),
    )


class CancelForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={**_TEXT, "rows": 3, "placeholder": "Reason for cancellation"})
    )
