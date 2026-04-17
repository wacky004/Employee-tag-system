from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceSession
from attendance.services import get_employee_tagging_state
from employees.models import Department, EmployeeProfile, Team
from tagging.models import TagLog, TagType

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


class EmployeeDashboardTaggingTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username="employee-dashboard",
            password="password123",
            email="employee-dashboard@example.com",
            role=User.Role.EMPLOYEE,
            first_name="Taylor",
        )
        EmployeeProfile.objects.create(
            user=self.employee,
            employee_code="EMP900",
            schedule_start_time=time(8, 0),
            schedule_end_time=time(17, 0),
            default_work_mode="WFH",
        )
        self._seed_tag_types()

    def test_employee_dashboard_shows_valid_initial_buttons(self):
        self.client.login(username="employee-dashboard", password="password123")

        response = self.client.get("/dashboard/employee/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["time_in_button"]["enabled"])
        self.assertTrue(response.context["time_in_button"]["visible"])
        self.assertFalse(response.context["time_out_button"]["visible"])
        self.assertEqual(len(response.context["tag_controls"]), 3)
        self.assertEqual(response.context["current_status"], "Not Tagged Yet")
        self.assertGreaterEqual(len(response.context["scheduled_hours_rows"]), 1)

    def test_employee_dashboard_post_creates_tag_log_and_updates_session(self):
        self.client.login(username="employee-dashboard", password="password123")

        response = self.client.post("/dashboard/employee/", {"tag_action": "TIME_IN"}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TagLog.objects.count(), 1)
        tag_log = TagLog.objects.get()
        self.assertEqual(tag_log.tag_type.code, "TIME_IN")
        self.assertEqual(tag_log.work_mode, "WFH")
        session = AttendanceSession.objects.get(employee=self.employee, work_date=timezone.localdate())
        self.assertIsNotNone(session.first_time_in)
        self.assertEqual(response.context["current_status"], "Currently Working")
        self.assertTrue(response.context["time_out_button"]["visible"])
        self.assertEqual(len(response.context["tag_controls"]), 3)

    def test_employee_history_tab_loads_by_date(self):
        self.client.login(username="employee-dashboard", password="password123")

        response = self.client.get("/dashboard/employee/?tab=history&history_start_date=2026-04-12&history_end_date=2026-04-14")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.context["history_start_date"]), "2026-04-12")
        self.assertEqual(str(response.context["history_end_date"]), "2026-04-14")

    def test_employee_dashboard_blocks_time_in_during_cooldown_after_time_out(self):
        self.client.login(username="employee-dashboard", password="password123")
        now = timezone.now()
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="TIME_IN"),
            work_date=timezone.localdate(),
            timestamp=now - timezone.timedelta(hours=1),
            work_mode="WFH",
            source="WEB",
        )
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="TIME_OUT"),
            work_date=timezone.localdate(),
            timestamp=now - timezone.timedelta(minutes=30),
            work_mode="WFH",
            source="WEB",
        )
        AttendanceSession.objects.create(
            employee=self.employee,
            work_date=timezone.localdate(),
            first_time_in=now - timezone.timedelta(hours=1),
            last_time_out=now - timezone.timedelta(minutes=30),
        )

        response = self.client.get("/dashboard/employee/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["time_in_button"]["enabled"])
        self.assertTrue(response.context["cooldown_active"])

    def test_employee_dashboard_allows_only_active_tag_end_when_auxiliary_tag_is_open(self):
        self.client.login(username="employee-dashboard", password="password123")
        work_date = timezone.localdate()
        now = timezone.now()
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="TIME_IN"),
            work_date=work_date,
            timestamp=now - timezone.timedelta(hours=1),
            work_mode="WFH",
            source="WEB",
        )
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="BIO_OUT"),
            work_date=work_date,
            timestamp=now - timezone.timedelta(minutes=5),
            work_mode="WFH",
            source="WEB",
        )
        AttendanceSession.objects.create(
            employee=self.employee,
            work_date=work_date,
            first_time_in=now - timezone.timedelta(hours=1),
            current_status=AttendanceSession.Status.BIO,
            work_mode="WFH",
        )

        response = self.client.get("/dashboard/employee/")
        controls = {item["key"]: item for item in response.context["tag_controls"]}

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["time_out_button"]["enabled"])
        self.assertFalse(controls["lunch"]["enabled"])
        self.assertFalse(controls["break"]["enabled"])
        self.assertTrue(controls["bio"]["enabled"])
        self.assertEqual(controls["bio"]["button_label"], "Bio End")

    def test_tagging_state_blocks_other_auxiliary_tags_while_one_is_active(self):
        work_date = timezone.localdate()
        now = timezone.now()
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="TIME_IN"),
            work_date=work_date,
            timestamp=now - timezone.timedelta(hours=1),
            work_mode="WFH",
            source="WEB",
        )
        TagLog.objects.create(
            employee=self.employee,
            tag_type=TagType.objects.get(code="LUNCH_OUT"),
            work_date=work_date,
            timestamp=now - timezone.timedelta(minutes=10),
            work_mode="WFH",
            source="WEB",
        )
        AttendanceSession.objects.create(
            employee=self.employee,
            work_date=work_date,
            first_time_in=now - timezone.timedelta(hours=1),
            current_status=AttendanceSession.Status.LUNCH,
            work_mode="WFH",
        )

        state = get_employee_tagging_state(self.employee, work_date)

        self.assertEqual(state["valid_codes"], ["LUNCH_IN"])

    def _seed_tag_types(self):
        tag_types = [
            ("TIME_IN", "Time In", TagType.Category.SHIFT, TagType.Direction.IN),
            ("TIME_OUT", "Time Out", TagType.Category.SHIFT, TagType.Direction.OUT),
            ("LUNCH_OUT", "Lunch Out", TagType.Category.LUNCH, TagType.Direction.OUT),
            ("LUNCH_IN", "Lunch In", TagType.Category.LUNCH, TagType.Direction.IN),
            ("BREAK_OUT", "Break Out", TagType.Category.BREAK, TagType.Direction.OUT),
            ("BREAK_IN", "Break In", TagType.Category.BREAK, TagType.Direction.IN),
            ("BIO_OUT", "Bio Out", TagType.Category.BIO, TagType.Direction.OUT),
            ("BIO_IN", "Bio In", TagType.Category.BIO, TagType.Direction.IN),
        ]
        for index, (code, name, category, direction) in enumerate(tag_types, start=1):
            TagType.objects.create(
                code=code,
                name=name,
                category=category,
                direction=direction,
                sort_order=index,
            )


class ModuleAccessManagementTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="module-super",
            password="password123",
            email="module-super@example.com",
            role=User.Role.SUPER_ADMIN,
        )
        self.user = User.objects.create_user(
            username="module-user",
            password="password123",
            email="module-user@example.com",
            role=User.Role.EMPLOYEE,
        )

    def test_super_admin_can_update_user_module_access(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("accounts:module-access"),
            {
                "user_id": self.user.id,
                "can_access_tagging": "on",
                "can_access_inventory": "on",
            },
            follow=True,
        )
        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.can_access_tagging)
        self.assertTrue(self.user.can_access_inventory)
        self.assertContains(response, "Module access updated")

    def test_admin_with_tagging_toggle_can_open_employee_tagging_dashboard(self):
        admin_user = User.objects.create_user(
            username="tag-admin",
            password="password123",
            email="tag-admin@example.com",
            role=User.Role.ADMIN,
            can_access_tagging=True,
        )
        EmployeeProfile.objects.create(
            user=admin_user,
            employee_code="TAG001",
            schedule_start_time=time(8, 0),
            schedule_end_time=time(17, 0),
            default_work_mode="ONSITE",
        )
        tag_types = [
            ("TIME_IN", "Time In", TagType.Category.SHIFT, TagType.Direction.IN),
            ("TIME_OUT", "Time Out", TagType.Category.SHIFT, TagType.Direction.OUT),
            ("LUNCH_OUT", "Lunch Out", TagType.Category.LUNCH, TagType.Direction.OUT),
            ("LUNCH_IN", "Lunch In", TagType.Category.LUNCH, TagType.Direction.IN),
            ("BREAK_OUT", "Break Out", TagType.Category.BREAK, TagType.Direction.OUT),
            ("BREAK_IN", "Break In", TagType.Category.BREAK, TagType.Direction.IN),
            ("BIO_OUT", "Bio Out", TagType.Category.BIO, TagType.Direction.OUT),
            ("BIO_IN", "Bio In", TagType.Category.BIO, TagType.Direction.IN),
        ]
        for index, (code, name, category, direction) in enumerate(tag_types, start=1):
            TagType.objects.create(
                code=code,
                name=name,
                category=category,
                direction=direction,
                sort_order=index,
            )

        self.client.force_login(admin_user)
        response = self.client.get(reverse("accounts:employee-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tagging Panel")
