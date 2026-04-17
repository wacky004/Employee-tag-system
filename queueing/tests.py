from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Company

User = get_user_model()


class QueueingDashboardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Queue Corp",
            code="QUEUECORP",
            can_use_queueing=True,
        )
        self.full_super_admin = User.objects.create_user(
            username="queue-root",
            password="password123",
            email="queue-root@example.com",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="queue-admin",
            password="password123",
            email="queue-admin@example.com",
            role=User.Role.ADMIN,
            company=self.company,
            can_access_queueing=True,
        )
        self.employee = User.objects.create_user(
            username="queue-employee",
            password="password123",
            email="queue-employee@example.com",
            role=User.Role.EMPLOYEE,
            company=self.company,
            can_access_queueing=True,
        )

    def test_full_super_admin_can_open_queueing_dashboard(self):
        self.client.force_login(self.full_super_admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Queueing System")

    def test_admin_with_queueing_access_can_open_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Queueing System")

    def test_employee_cannot_open_queueing_dashboard(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertRedirects(response, reverse("accounts:employee-dashboard"))

    def test_tenant_disabled_queueing_blocks_access(self):
        self.company.can_use_queueing = False
        self.company.save(update_fields=["can_use_queueing"])

        self.client.force_login(self.admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertRedirects(response, reverse("accounts:manager-dashboard"))

