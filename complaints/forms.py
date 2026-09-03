from django import forms

from .models import Complaint

_TEXT = {"class": "input"}


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["booking", "subject", "description"]
        widgets = {
            "subject": forms.TextInput(attrs=_TEXT),
            "description": forms.Textarea(attrs={**_TEXT, "rows": 5}),
            "booking": forms.Select(attrs=_TEXT),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["booking"].required = False
        if user is not None:
            if user.is_provider:
                self.fields["booking"].queryset = user.bookings_received.all()
            else:
                self.fields["booking"].queryset = user.bookings_made.all()


class ComplaintResolveForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["status", "resolution"]
        widgets = {
            "status": forms.Select(attrs=_TEXT),
            "resolution": forms.Textarea(attrs={**_TEXT, "rows": 4}),
        }
