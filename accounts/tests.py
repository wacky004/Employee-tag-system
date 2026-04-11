from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from attendance.models import AttendanceSession
from employees.models import Department, EmployeeProfile, Team

User = get_user_model()


class ManagerDashboardTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager1",
            password="password123",
            email="manager@example.com",
            role=User.Role.ADMIN,
        )
        self.department = Department.objects.create(name="Operations", code="OPS")
        self.team = Team.objects.create(name="Alpha", code="ALPHA", department=self.department, lead=self.manager)

        self.employee_working = self._create_employee("emp1", "E001", "Agent 1", "ONSITE")
        self.employee_lunch = self._create_employee("emp2", "E002", "Agent 2", "WFH")
        self.employee_no_time_in = self._create_employee("emp3", "E003", "Agent 3", "ONSITE")

        AttendanceSession.objects.create(
            employee=self.employee_working,
            work_date=date(2026, 4, 11),
            current_status=AttendanceSession.Status.WORKING,
            work_mode="ONSITE",
            first_time_in="2026-04-11T08:00:00Z",
        )
        AttendanceSession.objects.create(
            employee=self.employee_lunch,
            work_date=date(2026, 4, 11),
            current_status=AttendanceSession.Status.LUNCH,
            work_mode="WFH",
            first_time_in="2026-04-11T08:05:00Z",
            total_overbreak_minutes=5,
        )

    def test_manager_dashboard_groups_employees_by_status(self):
        self.client.login(username="manager1", password="password123")

        response = self.client.get("/dashboard/manager/?date=2026-04-11")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["currently_logged_in"]), 1)
        self.assertEqual(len(response.context["on_lunch"]), 1)
        self.assertEqual(len(response.context["not_timed_in"]), 1)
        self.assertEqual(len(response.context["overbreak_rows"]), 1)

    def test_manager_dashboard_filters_by_work_mode(self):
        self.client.login(username="manager1", password="password123")

        response = self.client.get("/dashboard/manager/?date=2026-04-11&work_mode=WFH")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["employee_rows"]), 1)
        self.assertEqual(response.context["employee_rows"][0]["employee_code"], "E002")

    def _create_employee(self, username, employee_code, first_name, work_mode):
        user = User.objects.create_user(
            username=username,
            password="password123",
            email=f"{username}@example.com",
            first_name=first_name,
            role=User.Role.EMPLOYEE,
        )
        EmployeeProfile.objects.create(
            user=user,
            employee_code=employee_code,
            department=self.department,
            team=self.team,
            default_work_mode=work_mode,
        )
        return user
