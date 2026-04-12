from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from attendance.models import AttendanceSession, OverbreakRecord
from employees.models import Department, EmployeeProfile, Team
from tagging.models import TagType

User = get_user_model()


class ReportCenterTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager-report",
            password="password123",
            email="manager-report@example.com",
            role=User.Role.ADMIN,
        )
        self.department = Department.objects.create(name="Operations", code="OPS")
        self.team = Team.objects.create(name="Support", code="SUP", department=self.department, lead=self.manager)
        self.employee = User.objects.create_user(
            username="employee-report",
            password="password123",
            email="employee-report@example.com",
            role=User.Role.EMPLOYEE,
            first_name="Jamie",
            last_name="Rivera",
        )
        EmployeeProfile.objects.create(
            user=self.employee,
            employee_code="EMP001",
            department=self.department,
            team=self.team,
            default_work_mode="ONSITE",
        )
        self.session = AttendanceSession.objects.create(
            employee=self.employee,
            work_date=date(2026, 4, 11),
            work_mode="ONSITE",
            total_work_minutes=450,
            total_lunch_minutes=60,
            total_break_minutes=20,
            total_bio_minutes=10,
            total_late_minutes=5,
            total_overbreak_minutes=5,
            missing_tag_pairs_count=1,
            has_incomplete_records=True,
        )
        tag_type = TagType.objects.create(
            code="BREAK_OUT",
            name="Break Out",
            category=TagType.Category.BREAK,
            direction=TagType.Direction.OUT,
        )
        OverbreakRecord.objects.create(
            employee=self.employee,
            attendance_session=self.session,
            tag_type=tag_type,
            started_at="2026-04-11T10:00:00Z",
            ended_at="2026-04-11T10:20:00Z",
            allowed_minutes=15,
            actual_minutes=20,
            excess_minutes=5,
        )

    def test_report_center_html(self):
        self.client.login(username="manager-report", password="password123")
        response = self.client.get("/reports/?report=daily&date=2026-04-11")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily Attendance Report")
        self.assertContains(response, "Jamie Rivera")
        self.assertContains(response, "07:30:00")
        self.assertContains(response, "01:00:00")

    def test_report_center_csv_export(self):
        self.client.login(username="manager-report", password="password123")
        response = self.client.get("/reports/?report=overbreak&date=2026-04-11&export=csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=\"overbreak-report.csv\"", response["Content-Disposition"])
