from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import TagLog, TagType

User = get_user_model()


class TaggingDashboardTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="supertagging",
            email="supertagging@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="admintagging",
            email="admintagging@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )
        self.employee = User.objects.create_user(
            username="employeetagging",
            email="employeetagging@example.com",
            password="pass12345",
            role=User.Role.EMPLOYEE,
        )
        self.tag_type = TagType.objects.create(
            code="TIME_IN",
            name="Time In",
            category=TagType.Category.SHIFT,
            direction=TagType.Direction.IN,
            is_active=True,
            sort_order=1,
        )

    def test_super_admin_can_open_tagging_dashboard(self):
        TagLog.objects.create(
            employee=self.employee,
            tag_type=self.tag_type,
            work_date=timezone.localdate(),
            timestamp=timezone.now(),
            source=TagLog.Source.WEB,
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("tagging:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee Tagging")
        self.assertContains(response, "Correction Review")
        self.assertContains(response, "Time In")

    def test_admin_is_redirected_away_from_tagging_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("tagging:dashboard"))

        self.assertRedirects(response, reverse("accounts:manager-dashboard"))

    def test_employee_with_tagging_toggle_can_open_tagging_dashboard(self):
        self.employee.can_access_tagging = True
        self.employee.save(update_fields=["can_access_tagging"])

        self.client.force_login(self.employee)
        response = self.client.get(reverse("tagging:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee Tagging")
