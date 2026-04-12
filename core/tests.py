from django.contrib.auth import get_user_model
from django.test import TestCase

from attendance.models import AttendanceSession
from auditlogs.models import AuditLog
from tagging.models import TagLog, TagType

from .models import SystemSetting

User = get_user_model()


class SuperAdminSettingsTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superadmin1",
            password="password123",
            email="superadmin@example.com",
            role=User.Role.SUPER_ADMIN,
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
