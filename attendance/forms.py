from django import forms

from tagging.models import TagType

from .models import CorrectionRequest


class CorrectionRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        tag_type_ids = [tag_type.pk for tag_type in TagType.effective_for_company(company)]
        self.fields["requested_tag_type"].queryset = TagType.objects.filter(pk__in=tag_type_ids).order_by("sort_order", "name")
        self.fields["details"].required = False

    class Meta:
        model = CorrectionRequest
        fields = [
            "request_type",
            "target_work_date",
            "action_type",
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


class CorrectionReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=(
            ("approve", "Approve"),
            ("reject", "Reject"),
        )
    )
    resolution_notes = forms.CharField(widget=forms.Textarea, required=False)
