from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class InventoryDashboardTests(TestCase):
    def test_super_admin_can_access_inventory_module(self):
        user = User.objects.create_user(
            username="superinventory",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Management")

    def test_admin_can_access_inventory_module(self):
        user = User.objects.create_user(
            username="managerinventory",
            password="pass12345",
            role=User.Role.ADMIN,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_employee_is_redirected_away_from_inventory_module(self):
        user = User.objects.create_user(
            username="employeeinventory",
            password="pass12345",
            role=User.Role.EMPLOYEE,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertRedirects(response, reverse("accounts:employee-dashboard"))
