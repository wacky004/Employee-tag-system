from django import forms

from .models import Employee, Equipment, EquipmentCategory, Supervisor


class SupervisorForm(forms.ModelForm):
    class Meta:
        model = Supervisor
        fields = [
            "full_name",
            "employee_code",
            "department",
            "job_title",
            "is_active",
        ]


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "full_name",
            "employee_code",
            "department",
            "team_name",
            "job_title",
            "supervisor",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supervisor"].queryset = Supervisor.objects.filter(is_active=True).order_by("full_name")


class EquipmentCategoryForm(forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = [
            "name",
            "code",
            "description",
            "is_active",
        ]


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "asset_code",
            "name",
            "category",
            "brand",
            "model",
            "serial_number",
            "status",
            "notes",
        ]
        labels = {
            "name": "Equipment name",
            "category": "Equipment category",
            "asset_code": "Asset code / company property code",
            "serial_number": "Serial number",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class EquipmentAssignmentForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none())
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    status = forms.ChoiceField(
        choices=[("", "Keep current status"), *Equipment.Status.choices],
        required=False,
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].queryset = Equipment.objects.order_by("asset_code", "name")
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True).order_by("full_name")

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get("equipment")
        employee = cleaned_data.get("employee")
        if equipment and employee and equipment.current_employee_id == employee.id:
            raise forms.ValidationError("This equipment is already assigned to the selected employee.")
        return cleaned_data
