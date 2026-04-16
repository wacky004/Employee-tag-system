from typing import cast

from django import forms
from django.db.models import Q
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
        queryset = Supervisor.objects.filter(is_active=True)
        if self.instance.pk and self.instance.supervisor_id:
            queryset = Supervisor.objects.filter(Q(is_active=True) | Q(pk=self.instance.supervisor_id))
        supervisor_field = cast(forms.ModelChoiceField, self.fields["supervisor"])
        supervisor_field.queryset = queryset.order_by("full_name")
        self.fields["is_active"].help_text = "Only active employees appear in equipment assignment dropdowns."
        if not self.is_bound and not self.instance.pk:
            self.fields["is_active"].initial = True


class EmployeeAssignSupervisorForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    supervisor = forms.ModelChoiceField(queryset=Supervisor.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        supervisor_field = cast(forms.ModelChoiceField, self.fields["supervisor"])
        employee_field.queryset = Employee.objects.select_related("supervisor").order_by("full_name", "employee_code")
        supervisor_field.queryset = Supervisor.objects.filter(is_active=True).order_by("full_name", "employee_code")


class EmployeeSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")


class InventoryWorkbookImportForm(forms.Form):
    workbook = forms.FileField(
        help_text="Upload the Excel workbook exported from the inventory module."
    )

    def clean_workbook(self):
        workbook = self.cleaned_data["workbook"]
        if not workbook.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Please upload an .xlsx workbook.")
        return workbook


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
        equipment_field = cast(forms.ModelChoiceField, self.fields["equipment"])
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        equipment_field.queryset = Equipment.objects.order_by("asset_code", "name")
        employee_field.queryset = Employee.objects.filter(is_active=True).order_by("full_name")
        employee_field.help_text = "Only active inventory employees are listed here."

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
        equipment_field = cast(forms.ModelChoiceField, self.fields["equipment"])
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        equipment_field.queryset = Equipment.objects.select_related("current_employee").order_by("asset_code", "name")
        employee_field.queryset = Employee.objects.filter(is_active=True).order_by("full_name", "employee_code")
        employee_field.help_text = "Only active inventory employees are listed here."

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
