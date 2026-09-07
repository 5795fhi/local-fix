from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i}") for i in range(5, 0, -1)],
        coerce=int,
        widget=forms.RadioSelect(attrs={"class": "star-radio"}),
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={"class": "input", "rows": 4, "placeholder": "Share your experience"}
            ),
        }
