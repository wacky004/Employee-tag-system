from typing import cast

from django import forms
from django.db.models import Q
from django.utils import timezone

from accounts.models import Company

from .models import Employee, Equipment, EquipmentCategory, Supervisor


class CompanyScopedFormMixin:
    company_model_field_name = "company"

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.company = getattr(user, "company", None)
        self.can_choose_company = bool(user and user.can_manage_companies())
        if self.company_model_field_name in self.fields:
            company_field = cast(forms.ModelChoiceField, self.fields[self.company_model_field_name])
            company_field.queryset = Company.objects.filter(is_active=True).order_by("name")
            if self.can_choose_company:
                company_field.required = False
                company_field.help_text = "Optional for platform users. Select a tenant to keep inventory records private."
                if not self.is_bound and not company_field.initial and self.instance.pk:
                    company_field.initial = getattr(self.instance, "company", None)
            else:
                company_field.widget = forms.HiddenInput()
                company_field.required = False
                company_field.initial = self.company

    def clean(self):
        cleaned_data = super().clean()
        if self.company_model_field_name not in self.fields:
            return cleaned_data
        if not self.can_choose_company:
            cleaned_data[self.company_model_field_name] = self.company
        return cleaned_data


class SupervisorForm(CompanyScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Supervisor
        fields = [
            "company",
            "full_name",
            "employee_code",
            "department",
            "job_title",
            "is_active",
        ]


class EmployeeForm(CompanyScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "company",
            "full_name",
            "employee_code",
            "department",
            "team_name",
            "job_title",
            "supervisor",
            "is_active",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        queryset = Supervisor.objects.filter(is_active=True)
        if self.company:
            queryset = queryset.filter(company=self.company)
        if self.instance.pk and self.instance.supervisor_id:
            queryset = Supervisor.objects.filter(Q(is_active=True) | Q(pk=self.instance.supervisor_id))
            if self.company:
                queryset = queryset.filter(company=self.company)
        supervisor_field = cast(forms.ModelChoiceField, self.fields["supervisor"])
        supervisor_field.queryset = queryset.order_by("full_name")
        self.fields["is_active"].help_text = "Only active employees appear in equipment assignment dropdowns."
        if not self.is_bound and not self.instance.pk:
            self.fields["is_active"].initial = True

    def clean(self):
        cleaned_data = super().clean()
        supervisor = cleaned_data.get("supervisor")
        company = cleaned_data.get("company") or self.company
        if supervisor and company and supervisor.company_id != company.id:
            self.add_error("supervisor", "Supervisor must belong to the same organization.")
        return cleaned_data


class EmployeeAssignSupervisorForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    supervisor = forms.ModelChoiceField(queryset=Supervisor.objects.none())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        company = getattr(user, "company", None)
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        supervisor_field = cast(forms.ModelChoiceField, self.fields["supervisor"])
        employee_queryset = Employee.objects.select_related("supervisor").order_by("full_name", "employee_code")
        supervisor_queryset = Supervisor.objects.filter(is_active=True).order_by("full_name", "employee_code")
        if company:
            employee_queryset = employee_queryset.filter(company=company)
            supervisor_queryset = supervisor_queryset.filter(company=company)
        employee_field.queryset = employee_queryset
        supervisor_field.queryset = supervisor_queryset


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


class EquipmentCategoryForm(CompanyScopedFormMixin, forms.ModelForm):
    class Meta:
        model = EquipmentCategory
        fields = [
            "company",
            "name",
            "code",
            "description",
            "is_active",
        ]


class EquipmentForm(CompanyScopedFormMixin, forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "company",
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        category_queryset = EquipmentCategory.objects.filter(is_active=True).order_by("name", "code")
        if self.company:
            category_queryset = category_queryset.filter(company=self.company)
        if self.instance.pk and self.instance.category_id:
            category_queryset = EquipmentCategory.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.category_id)
            ).order_by("name", "code")
            if self.company:
                category_queryset = category_queryset.filter(company=self.company)
        category_field = cast(forms.ModelChoiceField, self.fields["category"])
        category_field.queryset = category_queryset

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")
        company = cleaned_data.get("company") or self.company
        if category and company and category.company_id != company.id:
            self.add_error("category", "Equipment category must belong to the same organization.")
        return cleaned_data


class EquipmentAssignmentForm(forms.Form):
    equipment = forms.ModelChoiceField(queryset=Equipment.objects.none())
    employee = forms.ModelChoiceField(queryset=Employee.objects.none())
    status = forms.ChoiceField(
        choices=[("", "Keep current status"), *Equipment.Status.choices],
        required=False,
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        company = getattr(user, "company", None)
        equipment_field = cast(forms.ModelChoiceField, self.fields["equipment"])
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        equipment_queryset = Equipment.objects.order_by("asset_code", "name")
        employee_queryset = Employee.objects.filter(is_active=True).order_by("full_name")
        if company:
            equipment_queryset = equipment_queryset.filter(company=company)
            employee_queryset = employee_queryset.filter(company=company)
        equipment_field.queryset = equipment_queryset
        employee_field.queryset = employee_queryset
        employee_field.help_text = "Only active inventory employees are listed here."

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get("equipment")
        employee = cleaned_data.get("employee")
        if equipment and employee and equipment.company_id != employee.company_id:
            raise forms.ValidationError("Equipment and employee must belong to the same organization.")
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        company = getattr(user, "company", None)
        equipment_field = cast(forms.ModelChoiceField, self.fields["equipment"])
        employee_field = cast(forms.ModelChoiceField, self.fields["employee"])
        equipment_queryset = Equipment.objects.select_related("current_employee", "category").order_by(
            "asset_code", "name"
        )
        employee_queryset = Employee.objects.filter(is_active=True).order_by("full_name", "employee_code")
        if company:
            equipment_queryset = equipment_queryset.filter(company=company)
            employee_queryset = employee_queryset.filter(company=company)
        equipment_field.queryset = equipment_queryset
        employee_field.queryset = employee_queryset
        employee_field.help_text = "Only active inventory employees are listed here."

    def clean(self):
        cleaned_data = super().clean()
        equipment = cleaned_data.get("equipment")
        employee = cleaned_data.get("employee")
        allow_defective = cleaned_data.get("allow_defective_assignment")
        if not equipment:
            return cleaned_data
        if employee and equipment.company_id != employee.company_id:
            raise forms.ValidationError("Equipment and employee must belong to the same organization.")
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
