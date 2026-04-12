from django import forms

from tagging.models import TagType

from .models import CorrectionRequest


class CorrectionRequestForm(forms.ModelForm):
    class Meta:
        model = CorrectionRequest
        fields = [
            "request_type",
            "target_work_date",
            "requested_tag_type",
            "requested_timestamp",
            "requested_work_mode",
            "reason",
            "details",
        ]
        widgets = {
            "target_work_date": forms.DateInput(attrs={"type": "date"}),
            "requested_timestamp": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requested_tag_type"].queryset = TagType.objects.filter(is_active=True).order_by("sort_order", "name")


class CorrectionReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(
            ("approve", "Approve"),
            ("reject", "Reject"),
        )
    )
    resolution_notes = forms.CharField(widget=forms.Textarea, required=False)
