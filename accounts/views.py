from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View

from attendance.models import AttendanceSession
from employees.models import Department, EmployeeProfile, Team

User = get_user_model()


def get_dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return get_dashboard_url(self.request.user)


class DashboardRedirectView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(get_dashboard_url(request.user))


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(get_dashboard_url(self.request.user))
        return super().handle_no_permission()


class EmployeeDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/employee_dashboard.html"
    allowed_roles = (User.Role.EMPLOYEE,)


class ManagerDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/manager_dashboard.html"
    allowed_roles = (User.Role.ADMIN,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_date = self._get_selected_date()
        selected_team = self.request.GET.get("team", "").strip()
        selected_department = self.request.GET.get("department", "").strip()
        selected_employee = self.request.GET.get("employee", "").strip()
        selected_work_mode = self.request.GET.get("work_mode", "").strip()

        profiles = (
            EmployeeProfile.objects.select_related("user", "team", "department", "team__department")
            .filter(user__role=User.Role.EMPLOYEE, is_active=True, user__is_active=True)
            .order_by("user__first_name", "user__last_name", "employee_code")
        )

        if selected_team:
            profiles = profiles.filter(team_id=selected_team)
        if selected_department:
            profiles = profiles.filter(
                Q(department_id=selected_department) | Q(team__department_id=selected_department)
            )
        if selected_employee:
            profiles = profiles.filter(user_id=selected_employee)

        profile_list = list(profiles)
        employee_ids = [profile.user_id for profile in profile_list]

        sessions = AttendanceSession.objects.filter(
            employee_id__in=employee_ids,
            work_date=selected_date,
        ).select_related("employee")
        session_by_employee_id = {session.employee_id: session for session in sessions}

        employee_rows = []
        for profile in profile_list:
            session = session_by_employee_id.get(profile.user_id)
            row = self._build_employee_row(profile, session, selected_date)
            if selected_work_mode and row["work_mode"] != selected_work_mode:
                continue
            employee_rows.append(row)

        context.update(
            {
                "selected_date": selected_date,
                "selected_team": selected_team,
                "selected_department": selected_department,
                "selected_employee": selected_employee,
                "selected_work_mode": selected_work_mode,
                "teams": Team.objects.select_related("department").order_by("name"),
                "departments": Department.objects.order_by("name"),
                "employees": profile_list,
                "currently_logged_in": [row for row in employee_rows if row["bucket"] == "working"],
                "on_lunch": [row for row in employee_rows if row["bucket"] == "lunch"],
                "on_break": [row for row in employee_rows if row["bucket"] == "break"],
                "on_bio": [row for row in employee_rows if row["bucket"] == "bio"],
                "not_timed_in": [row for row in employee_rows if row["bucket"] == "not_timed_in"],
                "overbreak_rows": [row for row in employee_rows if row["is_overbreak"]],
                "timed_out": [row for row in employee_rows if row["bucket"] == "timed_out"],
                "summary_counts": {
                    "working": sum(1 for row in employee_rows if row["bucket"] == "working"),
                    "lunch": sum(1 for row in employee_rows if row["bucket"] == "lunch"),
                    "break": sum(1 for row in employee_rows if row["bucket"] == "break"),
                    "bio": sum(1 for row in employee_rows if row["bucket"] == "bio"),
                    "not_timed_in": sum(1 for row in employee_rows if row["bucket"] == "not_timed_in"),
                    "overbreak": sum(1 for row in employee_rows if row["is_overbreak"]),
                    "timed_out": sum(1 for row in employee_rows if row["bucket"] == "timed_out"),
                },
                "employee_rows": employee_rows,
            }
        )
        return context

    def _get_selected_date(self):
        raw_date = self.request.GET.get("date", "").strip()
        if raw_date:
            try:
                return date.fromisoformat(raw_date)
            except ValueError:
                pass
        return timezone.localdate()

    def _build_employee_row(self, profile, session, selected_date):
        department = profile.department or getattr(profile.team, "department", None)
        work_mode = (session.work_mode if session and session.work_mode else profile.default_work_mode) or ""
        bucket = self._resolve_bucket(session)

        return {
            "employee_id": profile.user_id,
            "employee_name": profile.user.get_full_name() or profile.user.username,
            "employee_code": profile.employee_code,
            "team": profile.team.name if profile.team else "-",
            "department": department.name if department else "-",
            "work_mode": work_mode or "-",
            "job_title": profile.job_title or "-",
            "bucket": bucket,
            "status_label": self._status_label(bucket),
            "is_overbreak": bool(session and session.total_overbreak_minutes > 0),
            "first_time_in": session.first_time_in if session else None,
            "final_time_out": session.last_time_out if session else None,
            "total_overbreak_minutes": session.total_overbreak_minutes if session else 0,
            "has_incomplete_records": bool(session and session.has_incomplete_records),
            "missing_tag_pairs_count": session.missing_tag_pairs_count if session else 0,
            "summary_notes": session.summary_notes if session else [],
            "selected_date": selected_date,
        }

    def _resolve_bucket(self, session):
        if not session or not session.first_time_in:
            return "not_timed_in"
        if session.last_time_out:
            return "timed_out"
        if session.current_status == AttendanceSession.Status.LUNCH:
            return "lunch"
        if session.current_status == AttendanceSession.Status.BREAK:
            return "break"
        if session.current_status == AttendanceSession.Status.BIO:
            return "bio"
        return "working"

    def _status_label(self, bucket):
        labels = {
            "working": "Currently Working",
            "lunch": "On Lunch",
            "break": "On Break",
            "bio": "On Bio",
            "not_timed_in": "Not Timed In",
            "timed_out": "Timed Out",
        }
        return labels.get(bucket, "Unknown")


class SuperAdminDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/super_admin_dashboard.html"
    allowed_roles = (User.Role.SUPER_ADMIN,)
