from django import forms

from .models import Equipment, InventoryUser


class InventorySupervisorForm(forms.ModelForm):
    class Meta:
        model = InventoryUser
        fields = [
            "full_name",
            "employee_code",
            "department_name",
            "team_name",
            "job_title",
            "is_active",
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_supervisor = True
        instance.supervisor = None
        if commit:
            instance.save()
        return instance


class InventoryUserForm(forms.ModelForm):
    class Meta:
        model = InventoryUser
        fields = [
            "full_name",
            "employee_code",
            "department_name",
            "team_name",
            "job_title",
            "supervisor",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supervisor"].queryset = InventoryUser.objects.filter(
            is_supervisor=True,
            is_active=True,
        ).order_by("full_name")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_supervisor = False
        if commit:
            instance.save()
        return instance


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "asset_code",
            "name",
            "category",
            "brand",
            "model_number",
            "serial_number",
            "status",
            "notes",
        ]


class EquipmentAssignmentForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none())
    holder = forms.ModelChoiceField(queryset=InventoryUser.objects.none())
    status = forms.ChoiceField(
        choices=[("", "Keep current status"), *Equipment.Status.choices],
        required=False,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].queryset = Equipment.objects.order_by("asset_code", "name")
        self.fields["holder"].queryset = InventoryUser.objects.filter(is_active=True).order_by("full_name")

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get("equipment")
        holder = cleaned_data.get("holder")
        if equipment and holder and equipment.current_holder_id == holder.id:
            raise forms.ValidationError("This equipment is already assigned to the selected employee.")
        return cleaned_data
