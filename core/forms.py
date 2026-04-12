from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Role
from employees.models import Department, EmployeeProfile, Team

from .models import SystemSetting

User = get_user_model()


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = [
            "company_name",
            "default_timezone",
            "required_work_minutes",
            "lunch_minutes_allowed",
            "break_minutes_allowed",
            "bio_minutes_allowed",
            "late_after_time",
            "late_grace_minutes",
            "overbreak_grace_minutes",
            "allow_employee_log_edit",
            "allow_admin_log_edit",
            "allow_duplicate_tags",
            "require_work_mode_on_time_in",
            "allow_multiple_tag_clicks",
        ]
        widgets = {
            "late_after_time": forms.TimeInput(attrs={"type": "time"}),
        }


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "description"]


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "code", "description", "department", "lead"]


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["code", "name", "description", "is_active"]


class EmployeeProfileForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "last_name", "username"),
    )

    class Meta:
        model = EmployeeProfile
        fields = [
            "user",
            "employee_code",
            "department",
            "team",
            "job_title",
            "timezone",
            "default_work_mode",
            "hire_date",
            "is_active",
        ]
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_user(self):
        user = self.cleaned_data["user"]
        qs = EmployeeProfile.objects.filter(user=user)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This user already has an employee profile.")
        return user
