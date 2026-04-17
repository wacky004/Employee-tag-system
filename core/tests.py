from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Company
from attendance.models import AttendanceSession
from auditlogs.models import AuditLog
from employees.models import Department, EmployeeProfile, Team
from tagging.models import TagLog, TagType

from .models import SystemSetting

User = get_user_model()


class SuperAdminSettingsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Agency VA PH", code="AGENCYPH")
        self.super_admin = User.objects.create_user(
            username="superadmin1",
            password="password123",
            email="superadmin@example.com",
            role=User.Role.SUPER_ADMIN,
            company=self.company,
            limit_to_enabled_modules=True,
            can_access_tagging=True,
        )

    def test_settings_page_is_available_to_super_admin(self):
        self.client.login(username="superadmin1", password="password123")
        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Super Admin Settings")

    def test_super_admin_can_update_system_settings(self):
        self.client.login(username="superadmin1", password="password123")

        response = self.client.post(
            "/settings/",
            {
                "action": "system-settings",
                "company_name": "My Attendance System",
                "default_timezone": "Asia/Manila",
                "required_work_minutes": 510,
                "time_in_cooldown_hours": 6,
                "lunch_minutes_allowed": 50,
                "break_minutes_allowed": 20,
                "bio_minutes_allowed": 12,
                "late_after_time": "09:05",
                "late_grace_minutes": 5,
                "overbreak_grace_minutes": 3,
                "allow_employee_log_edit": "on",
                "allow_admin_log_edit": "on",
                "allow_duplicate_tags": "",
                "require_work_mode_on_time_in": "on",
                "allow_multiple_tag_clicks": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        setting = SystemSetting.objects.get()
        self.assertEqual(setting.company_name, "My Attendance System")
        self.assertEqual(setting.required_work_minutes, 510)
        self.assertEqual(setting.time_in_cooldown_hours, 6)
        self.assertEqual(setting.lunch_minutes_allowed, 50)
        self.assertEqual(setting.late_grace_minutes, 5)

    def test_super_admin_can_reset_employee_attendance(self):
        employee = User.objects.create_user(
            username="employee-reset",
            password="password123",
            email="employee-reset@example.com",
            role=User.Role.EMPLOYEE,
            company=self.company,
        )
        tag_type = TagType.objects.create(
            code="TIME_IN",
            name="Time In",
            category="SHIFT",
            direction="IN",
        )
        TagLog.objects.create(
            employee=employee,
            tag_type=tag_type,
            work_date="2026-04-12",
            timestamp="2026-04-12T09:00:00Z",
            source="WEB",
        )
        AttendanceSession.objects.create(employee=employee, work_date="2026-04-12")

        self.client.login(username="superadmin1", password="password123")
        response = self.client.post(
            "/settings/",
            {
                "action": "attendance-reset",
                "user": employee.id,
                "work_date": "2026-04-12",
                "reason": "Reset for correction.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TagLog.objects.filter(employee=employee).count(), 0)
        self.assertEqual(AttendanceSession.objects.filter(employee=employee).count(), 0)
        self.assertTrue(AuditLog.objects.filter(action="ATTENDANCE_RESET").exists())

    def test_settings_page_only_shows_profiles_from_current_company(self):
        same_company_user = User.objects.create_user(
            username="tenant-user",
            password="password123",
            email="tenant-user@example.com",
            role=User.Role.EMPLOYEE,
            company=self.company,
        )
        other_company = Company.objects.create(name="Agency VA US", code="AGENCYUS")
        other_company_user = User.objects.create_user(
            username="other-user",
            password="password123",
            email="other-user@example.com",
            role=User.Role.EMPLOYEE,
            company=other_company,
        )
        department = Department.objects.create(name="Operations Tenant", code="OPS-TENANT", company=self.company)
        other_department = Department.objects.create(name="Operations Other", code="OPS-OTHER", company=other_company)
        EmployeeProfile.objects.create(user=same_company_user, employee_code="TEN-001", department=department)
        EmployeeProfile.objects.create(user=other_company_user, employee_code="OTH-001", department=other_department)

        self.client.login(username="superadmin1", password="password123")
        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tenant-user")
        self.assertNotContains(response, "other-user")

    def test_super_admin_can_remove_department_team_and_profile_for_current_company(self):
        employee_user = User.objects.create_user(
            username="remove-user",
            password="password123",
            email="remove-user@example.com",
            role=User.Role.EMPLOYEE,
            company=self.company,
        )
        department = Department.objects.create(name="Remove Department", code="REMOVE-DEPT", company=self.company)
        team = Team.objects.create(name="Remove Team", code="REMOVE-TEAM", company=self.company, department=department)
        profile = EmployeeProfile.objects.create(user=employee_user, employee_code="REM-001", department=department, team=team)

        self.client.login(username="superadmin1", password="password123")

        profile_response = self.client.post(
            "/settings/",
            {"action": "delete-employee-profile", "profile_id": profile.id},
            follow=True,
        )
        team_response = self.client.post(
            "/settings/",
            {"action": "delete-team", "team_id": team.id},
            follow=True,
        )
        department_response = self.client.post(
            "/settings/",
            {"action": "delete-department", "department_id": department.id},
            follow=True,
        )

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(team_response.status_code, 200)
        self.assertEqual(department_response.status_code, 200)
        self.assertFalse(EmployeeProfile.objects.filter(pk=profile.id).exists())
        self.assertFalse(Team.objects.filter(pk=team.id).exists())
        self.assertFalse(Department.objects.filter(pk=department.id).exists())
