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
            bookings = (
                user.bookings_received.all()
                if user.is_provider
                else user.bookings_made.all()
            ).select_related("provider", "customer", "category")
            self.fields["booking"].queryset = bookings
            self.fields["booking"].choices = [
                ("", "---------"),
                *(
                    (
                        b.pk,
                        f"#{b.pk} · {b.category or 'Service'}"
                        f" · with {(b.provider if not user.is_provider else b.customer).display_name}"
                        f" · {b.scheduled_for:%d %b %Y}",
                    )
                    for b in bookings[:50]
                ),
            ]


class ComplaintResolveForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["status", "resolution"]
        widgets = {
            "status": forms.Select(attrs=_TEXT),
            "resolution": forms.Textarea(attrs={**_TEXT, "rows": 4}),
        }
