from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Role
from auditlogs.services import create_audit_log
from attendance.models import AttendanceSession, CorrectionRequest, OverbreakRecord
from tagging.models import TagLog
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
            "time_in_cooldown_hours",
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

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        departments = Department.objects.order_by("name")
        leads = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        if company is not None:
            departments = departments.filter(company=company)
            leads = leads.filter(company=company)
        self.fields["department"].queryset = departments
        self.fields["lead"].queryset = leads


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
            "schedule_start_time",
            "schedule_end_time",
            "default_work_mode",
            "hire_date",
            "is_active",
        ]
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "schedule_start_time": forms.TimeInput(attrs={"type": "time"}),
            "schedule_end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        departments = Department.objects.order_by("name")
        teams = Team.objects.select_related("department").order_by("name")
        if company is not None:
            users = users.filter(company=company)
            departments = departments.filter(company=company)
            teams = teams.filter(company=company)
        self.fields["user"].queryset = users
        self.fields["department"].queryset = departments
        self.fields["team"].queryset = teams

    def clean_user(self):
        user = self.cleaned_data["user"]
        qs = EmployeeProfile.objects.filter(user=user)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This user already has an employee profile.")
        return user


class AttendanceResetForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "last_name", "username"),
        label="Employee",
    )
    work_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        company = kwargs.pop("company", None)
        super().__init__(*args, **kwargs)
        users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        if company is not None:
            users = users.filter(company=company)
        self.fields["user"].queryset = users

    def reset_attendance(self, actor):
        user = self.cleaned_data["user"]
        work_date = self.cleaned_data["work_date"]
        reason = self.cleaned_data["reason"]

        tag_logs = TagLog.objects.filter(employee=user, work_date=work_date)
        tag_log_ids = list(tag_logs.values_list("id", flat=True))
        sessions = AttendanceSession.objects.filter(employee=user, work_date=work_date)
        session_ids = list(sessions.values_list("id", flat=True))
        overbreak_ids = list(
            OverbreakRecord.objects.filter(attendance_session__in=sessions).values_list("id", flat=True)
        )
        correction_ids = list(
            CorrectionRequest.objects.filter(employee=user, target_work_date=work_date).values_list("id", flat=True)
        )

        OverbreakRecord.objects.filter(attendance_session__in=sessions).delete()
        CorrectionRequest.objects.filter(employee=user, target_work_date=work_date).delete()
        tag_logs.delete()
        sessions.delete()

        create_audit_log(
            actor=actor,
            employee=user,
            action="ATTENDANCE_RESET",
            target_model="AttendanceSession",
            target_id=f"{user.id}:{work_date.isoformat()}",
            description="Super Admin reset attendance records for a work date.",
            changes={
                "deleted_tag_logs": tag_log_ids,
                "deleted_sessions": session_ids,
                "deleted_overbreaks": overbreak_ids,
                "deleted_corrections": correction_ids,
            },
            metadata={"reason": reason, "work_date": work_date.isoformat()},
        )
