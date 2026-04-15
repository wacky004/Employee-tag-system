from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Equipment, EquipmentAssignment, InventoryUser

User = get_user_model()


class InventoryDashboardTests(TestCase):
    def test_super_admin_can_access_inventory_module(self):
        user = User.objects.create_user(
            username="superinventory",
            email="superinventory@example.com",
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
            email="managerinventory@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_employee_is_redirected_away_from_inventory_module(self):
        user = User.objects.create_user(
            username="employeeinventory",
            email="employeeinventory@example.com",
            password="pass12345",
            role=User.Role.EMPLOYEE,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertRedirects(response, reverse("accounts:employee-dashboard"))

    def test_super_admin_can_create_inventory_user_without_auth_login(self):
        user = User.objects.create_user(
            username="supercreate",
            email="supercreate@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "create_user",
                "user-full_name": "Jane Holder",
                "user-employee_code": "INV-001",
                "user-department_name": "Operations",
                "user-team_name": "Warehouse",
                "user-job_title": "Storekeeper",
                "user-is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("inventory:dashboard"))
        self.assertTrue(InventoryUser.objects.filter(employee_code="INV-001").exists())
        self.assertFalse(User.objects.filter(username="INV-001").exists())

    def test_super_admin_can_assign_equipment_and_history_is_preserved(self):
        user = User.objects.create_user(
            username="superassign",
            email="superassign@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        holder_one = InventoryUser.objects.create(full_name="User One", employee_code="INV-100")
        holder_two = InventoryUser.objects.create(full_name="User Two", employee_code="INV-101")
        equipment = Equipment.objects.create(
            asset_code="LAP-001",
            name="Laptop",
            status=Equipment.Status.BRAND_NEW,
        )

        self.client.force_login(user)
        first_response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "assign_equipment",
                "assignment-equipment": equipment.id,
                "assignment-holder": holder_one.id,
                "assignment-status": Equipment.Status.USED,
                "assignment-notes": "Initial assignment",
            },
        )
        equipment.refresh_from_db()

        self.assertRedirects(first_response, reverse("inventory:dashboard"))
        self.assertEqual(equipment.current_holder, holder_one)
        self.assertEqual(equipment.status, Equipment.Status.USED)

        second_response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "assign_equipment",
                "assignment-equipment": equipment.id,
                "assignment-holder": holder_two.id,
                "assignment-status": Equipment.Status.TO_BE_CHECKED,
                "assignment-notes": "Transferred to second holder",
            },
        )
        equipment.refresh_from_db()
        assignments = list(EquipmentAssignment.objects.filter(equipment=equipment))

        self.assertRedirects(second_response, reverse("inventory:dashboard"))
        self.assertEqual(equipment.current_holder, holder_two)
        self.assertEqual(equipment.status, Equipment.Status.TO_BE_CHECKED)
        self.assertEqual(len(assignments), 2)
        self.assertIsNotNone(assignments[1].returned_at)
