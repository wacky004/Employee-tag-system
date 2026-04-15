from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Employee, Equipment, EquipmentAssignment, EquipmentCategory, EquipmentHistoryLog, Supervisor

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

    def test_super_admin_can_create_employee_without_auth_login(self):
        user = User.objects.create_user(
            username="supercreate",
            email="supercreate@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        supervisor = Supervisor.objects.create(
            full_name="Supervisor One",
            employee_code="SUP-001",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "create_employee",
                "employee-full_name": "Jane Holder",
                "employee-employee_code": "EMP-001",
                "employee-department": "Operations",
                "employee-team_name": "Warehouse",
                "employee-job_title": "Storekeeper",
                "employee-supervisor": supervisor.id,
                "employee-is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("inventory:dashboard"))
        self.assertTrue(Employee.objects.filter(employee_code="EMP-001").exists())
        self.assertFalse(User.objects.filter(username="EMP-001").exists())

    def test_super_admin_can_assign_equipment_and_history_is_preserved(self):
        user = User.objects.create_user(
            username="superassign",
            email="superassign@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        category = EquipmentCategory.objects.create(name="Laptop", code="LAPTOP")
        employee_one = Employee.objects.create(full_name="User One", employee_code="EMP-100")
        employee_two = Employee.objects.create(full_name="User Two", employee_code="EMP-101")
        equipment = Equipment.objects.create(
            asset_code="LAP-001",
            name="Laptop",
            category=category,
            status=Equipment.Status.BRANDNEW,
        )

        self.client.force_login(user)
        first_response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "assign_equipment",
                "assignment-equipment": equipment.id,
                "assignment-employee": employee_one.id,
                "assignment-status": Equipment.Status.USED,
                "assignment-remarks": "Initial assignment",
            },
        )
        equipment.refresh_from_db()

        self.assertRedirects(first_response, reverse("inventory:dashboard"))
        self.assertEqual(equipment.current_employee, employee_one)
        self.assertEqual(equipment.status, Equipment.Status.USED)

        second_response = self.client.post(
            reverse("inventory:dashboard"),
            {
                "inventory_action": "assign_equipment",
                "assignment-equipment": equipment.id,
                "assignment-employee": employee_two.id,
                "assignment-status": Equipment.Status.TO_BE_CHECKED,
                "assignment-remarks": "Transferred to second holder",
            },
        )
        equipment.refresh_from_db()
        assignments = list(EquipmentAssignment.objects.filter(equipment=equipment))
        history_logs = list(EquipmentHistoryLog.objects.filter(equipment=equipment))

        self.assertRedirects(second_response, reverse("inventory:dashboard"))
        self.assertEqual(equipment.current_employee, employee_two)
        self.assertEqual(equipment.status, Equipment.Status.TO_BE_CHECKED)
        self.assertEqual(len(assignments), 2)
        self.assertIsNotNone(assignments[1].returned_at)
        self.assertGreaterEqual(len(history_logs), 3)


class EquipmentCreateModuleTests(TestCase):
    def test_super_admin_can_open_equipment_create_page(self):
        user = User.objects.create_user(
            username="superequipment",
            email="superequipment@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:equipment-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Equipment")

    def test_admin_cannot_access_equipment_create_page(self):
        user = User.objects.create_user(
            username="adminequipment",
            email="adminequipment@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:equipment-create"))

        self.assertRedirects(response, reverse("accounts:manager-dashboard"))

    def test_super_admin_can_create_equipment_record(self):
        user = User.objects.create_user(
            username="supercreateequipment",
            email="supercreateequipment@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        category = EquipmentCategory.objects.create(name="Laptop", code="LAPTOP")

        self.client.force_login(user)
        response = self.client.post(
            reverse("inventory:equipment-create"),
            {
                "name": "Dell Latitude 7440",
                "category": category.id,
                "brand": "Dell",
                "model": "Latitude 7440",
                "serial_number": "DL-7440-001",
                "asset_code": "COMP-0001",
                "status": Equipment.Status.BRANDNEW,
                "notes": "Newly received office laptop",
            },
        )

        self.assertRedirects(response, reverse("inventory:equipment-create"))
        self.assertTrue(
            Equipment.objects.filter(
                asset_code="COMP-0001",
                name="Dell Latitude 7440",
                status=Equipment.Status.BRANDNEW,
            ).exists()
        )
