from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
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

    def test_func(self):
        return self.request.user.role == User.Role.SUPER_ADMIN and self.request.user.has_tagging_module_access()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        setting = self._get_setting()
        edit_profile = self._get_edit_profile()
        company = self._current_company()
        context.update(
            {
                "setting": setting,
                "system_form": kwargs.get("system_form") or SystemSettingForm(instance=setting),
                "department_form": kwargs.get("department_form") or DepartmentForm(),
                "team_form": kwargs.get("team_form") or TeamForm(company=company),
                "role_form": kwargs.get("role_form") or RoleForm(),
                "employee_profile_form": kwargs.get("employee_profile_form")
                or EmployeeProfileForm(instance=edit_profile, company=company),
                "attendance_reset_form": kwargs.get("attendance_reset_form") or AttendanceResetForm(company=company),
                "editing_profile": edit_profile,
                "departments": self._departments_queryset(),
                "teams": self._teams_queryset(),
                "roles": Role.objects.order_by("name"),
                "employee_profiles": self._employee_profiles_queryset(),
                "current_company": company,
                "show_platform_admin": self.request.user.can_manage_companies(),
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
        if action == "delete-employee-profile":
            return self._delete_employee_profile()
        if action == "attendance-reset":
            return self._reset_attendance()
        if action == "delete-department":
            return self._delete_department()
        if action == "delete-team":
            return self._delete_team()
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
            department = form.save(commit=False)
            department.company = self._current_company()
            department.save()
            messages.success(self.request, "Department saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(department_form=form))

    def _save_team(self):
        form = TeamForm(self.request.POST, company=self._current_company())
        if form.is_valid():
            team = form.save(commit=False)
            team.company = self._current_company()
            team.save()
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
        form = EmployeeProfileForm(self.request.POST, instance=instance, company=self._current_company())
        if form.is_valid():
            profile = form.save()
            messages.success(self.request, f"Employee profile for {profile.user} saved.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(employee_profile_form=form, editing_profile=instance))

    def _delete_employee_profile(self):
        profile = get_object_or_404(self._employee_profiles_queryset(), pk=self.request.POST.get("profile_id"))
        profile_name = profile.user.get_full_name() or profile.user.username
        profile.delete()
        messages.success(self.request, f"Employee profile for {profile_name} removed.")
        return redirect("core:settings")

    def _reset_attendance(self):
        form = AttendanceResetForm(self.request.POST, company=self._current_company())
        if form.is_valid():
            form.reset_attendance(self.request.user)
            messages.success(self.request, "Attendance reset completed.")
            return redirect("core:settings")
        return self.render_to_response(self.get_context_data(attendance_reset_form=form))

    def _get_setting(self):
        company = self._current_company()
        setting = SystemSetting.objects.filter(company=company).order_by("id").first()
        if setting:
            return setting
        company_name = company.name if company else "AquiSo Platform"
        return SystemSetting.objects.create(company=company, company_name=company_name)

    def _get_edit_profile(self):
        profile_id = self.request.GET.get("edit_profile") or self.request.POST.get("profile_id")
        if not profile_id:
            return None
        return get_object_or_404(self._employee_profiles_queryset(), pk=profile_id)

    def _current_company(self):
        return self.request.user.company if self.request.user.company_id else None

    def _departments_queryset(self):
        departments = Department.objects.order_by("name")
        company = self._current_company()
        if company is not None:
            departments = departments.filter(company=company)
        return departments

    def _teams_queryset(self):
        teams = Team.objects.select_related("department", "lead").order_by("name")
        company = self._current_company()
        if company is not None:
            teams = teams.filter(company=company)
        return teams

    def _employee_profiles_queryset(self):
        profiles = EmployeeProfile.objects.select_related(
            "user", "department", "team", "team__department"
        ).order_by("employee_code")
        company = self._current_company()
        if company is not None:
            profiles = profiles.filter(user__company=company)
        return profiles

    def _delete_department(self):
        department = get_object_or_404(self._departments_queryset(), pk=self.request.POST.get("department_id"))
        department_name = department.name
        department.delete()
        messages.success(self.request, f"Department {department_name} removed.")
        return redirect("core:settings")

    def _delete_team(self):
        team = get_object_or_404(self._teams_queryset(), pk=self.request.POST.get("team_id"))
        team_name = team.name
        team.delete()
        messages.success(self.request, f"Team {team_name} removed.")
        return redirect("core:settings")
