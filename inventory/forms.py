from django import forms
from django.utils import timezone

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


class EmployeeAssignSupervisorForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    supervisor = forms.ModelChoiceField(queryset=Supervisor.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.select_related("supervisor").order_by("full_name", "employee_code")
        self.fields["supervisor"].queryset = Supervisor.objects.filter(is_active=True).order_by("full_name", "employee_code")


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


class EquipmentAssignmentCreateForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none())
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    assigned_at = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    allow_defective_assignment = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment"].queryset = Equipment.objects.select_related("current_employee").order_by("asset_code", "name")
        self.fields["employee"].queryset = Employee.objects.filter(is_active=True).order_by("full_name", "employee_code")

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get("equipment")
        allow_defective = cleaned_data.get("allow_defective_assignment")
        if not equipment:
            return cleaned_data
        if equipment.current_employee_id:
            raise forms.ValidationError("This equipment is already actively assigned to another employee.")
        if equipment.status == Equipment.Status.DEFECTIVE and not allow_defective:
            raise forms.ValidationError("Defective equipment cannot be assigned unless explicitly allowed.")
        return cleaned_data


class EquipmentReturnForm(forms.Form):
    returned_at = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
