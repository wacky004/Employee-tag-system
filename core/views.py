from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from accounts.models import Role
from accounts.views import RoleRequiredMixin
from employees.models import Department, EmployeeProfile, Team

from .forms import AttendanceResetForm, DepartmentForm, EmployeeProfileForm, RoleForm, SystemSettingForm, TeamForm
from .models import SystemSetting

User = get_user_model()


class SuperAdminSettingsView(RoleRequiredMixin, TemplateView):
    template_name = "core/settings_center.html"
    allowed_roles = (User.Role.SUPER_ADMIN,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        setting = self._get_setting()
        edit_profile = self._get_edit_profile()
        context.update(
            {
                "setting": setting,
                "system_form": kwargs.get("system_form") or SystemSettingForm(instance=setting),
                "department_form": kwargs.get("department_form") or DepartmentForm(),
                "team_form": kwargs.get("team_form") or TeamForm(),
                "role_form": kwargs.get("role_form") or RoleForm(),
                "employee_profile_form": kwargs.get("employee_profile_form")
                or EmployeeProfileForm(instance=edit_profile),
                "attendance_reset_form": kwargs.get("attendance_reset_form") or AttendanceResetForm(),
                "editing_profile": edit_profile,
                "departments": Department.objects.order_by("name"),
                "teams": Team.objects.select_related("department", "lead").order_by("name"),
                "roles": Role.objects.order_by("name"),
                "employee_profiles": EmployeeProfile.objects.select_related(
                    "user", "department", "team", "team__department"
                ).order_by("employee_code"),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "system-settings":
            return self._save_system_settings()
        if action == "department":
            return self._save_department()
        if action == "team":
            return self._save_team()
        if action == "role":
            return self._save_role()
        if action == "employee-profile":
            return self._save_employee_profile()
        if action == "attendance-reset":
            return self._reset_attendance()
        messages.error(request, "Unknown settings action.")
        return redirect("core:settings")

    def _save_system_settings(self):
        setting = self._get_setting()
        form = SystemSettingForm(self.request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(self.request, "System settings updated.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(system_form=form))

    def _save_department(self):
        form = DepartmentForm(self.request.POST)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Department saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(department_form=form))

    def _save_team(self):
        form = TeamForm(self.request.POST)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Team saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(team_form=form))

    def _save_role(self):
        form = RoleForm(self.request.POST)
        if form.is_valid():
            form.save()
            messages.success(self.request, "Role saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(role_form=form))

    def _save_employee_profile(self):
        instance = self._get_edit_profile()
        form = EmployeeProfileForm(self.request.POST, instance=instance)
        if form.is_valid():
            profile = form.save()
            messages.success(self.request, f"Employee profile for {profile.user} saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(employee_profile_form=form, editing_profile=instance))

    def _reset_attendance(self):
        form = AttendanceResetForm(self.request.POST)
        if form.is_valid():
            form.reset_attendance(self.request.user)
            messages.success(self.request, "Attendance reset completed.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(attendance_reset_form=form))

    def _get_setting(self):
        return SystemSetting.objects.order_by("id").first() or SystemSetting.objects.create()

    def _get_edit_profile(self):
        profile_id = self.request.GET.get("edit_profile") or self.request.POST.get("profile_id")
        if not profile_id:
            return None
        return get_object_or_404(EmployeeProfile, pk=profile_id)
