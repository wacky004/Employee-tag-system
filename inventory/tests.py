from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class EquipmentAssignmentModuleTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superassignmodule",
            email="superassignmodule@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="adminassignmodule",
            email="adminassignmodule@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )
        self.employee = Employee.objects.create(full_name="Employee Assign", employee_code="EMP-900")
        self.equipment = Equipment.objects.create(
            asset_code="EQ-900",
            name="Monitor",
            status=Equipment.Status.UNUSED,
        )

    def test_super_admin_can_assign_equipment(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": self.equipment.id,
                "employee": self.employee.id,
                "assigned_at": "2026-04-15T09:00",
                "notes": "Assigned for workstation use",
            },
        )
        self.equipment.refresh_from_db()
        assignment = EquipmentAssignment.objects.get(equipment=self.equipment)
        history = EquipmentHistoryLog.objects.filter(equipment=self.equipment, action=EquipmentHistoryLog.Action.ASSIGNED)

        self.assertRedirects(response, reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))
        self.assertEqual(self.equipment.current_employee, self.employee)
        self.assertEqual(assignment.employee, self.employee)
        self.assertEqual(assignment.remarks, "Assigned for workstation use")
        self.assertTrue(history.exists())

    def test_cannot_assign_equipment_when_already_active(self):
        other_employee = Employee.objects.create(full_name="Other Employee", employee_code="EMP-901")
        EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=other_employee,
            assigned_by=self.super_admin,
        )
        self.equipment.current_employee = other_employee
        self.equipment.save(update_fields=["current_employee"])

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": self.equipment.id,
                "employee": self.employee.id,
                "assigned_at": "2026-04-15T10:00",
                "notes": "Second assignment attempt",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already actively assigned")

    def test_cannot_assign_defective_equipment_without_override(self):
        self.equipment.status = Equipment.Status.DEFECTIVE
        self.equipment.save(update_fields=["status"])

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": self.equipment.id,
                "employee": self.employee.id,
                "assigned_at": "2026-04-15T10:00",
                "notes": "Attempted defective assignment",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Defective equipment cannot be assigned")

    def test_can_assign_defective_equipment_with_override(self):
        self.equipment.status = Equipment.Status.DEFECTIVE
        self.equipment.save(update_fields=["status"])

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": self.equipment.id,
                "employee": self.employee.id,
                "assigned_at": "2026-04-15T11:00",
                "notes": "Allowed defective assignment",
                "allow_defective_assignment": "on",
            },
        )

        self.assertRedirects(response, reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))

    def test_super_admin_can_return_equipment_and_create_history_log(self):
        assignment = EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
        )
        self.equipment.current_employee = self.employee
        self.equipment.save(update_fields=["current_employee"])

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}),
            {
                "return-returned_at": "2026-04-16T09:30",
                "return-notes": "Returned after project completion",
            },
        )
        assignment.refresh_from_db()
        self.equipment.refresh_from_db()

        self.assertRedirects(response, reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))
        self.assertIsNone(self.equipment.current_employee)
        self.assertIsNotNone(assignment.returned_at)
        self.assertTrue(
            EquipmentHistoryLog.objects.filter(
                equipment=self.equipment,
                action=EquipmentHistoryLog.Action.RETURNED,
            ).exists()
        )

    def test_equipment_detail_shows_current_holder(self):
        EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
        )
        self.equipment.current_employee = self.employee
        self.equipment.save(update_fields=["current_employee"])

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))

        self.assertContains(response, "Current Holder")
        self.assertContains(response, self.employee.full_name)

    def test_equipment_detail_shows_assignment_history_section(self):
        assignment = EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
            remarks="Issued for office use",
        )
        EquipmentHistoryLog.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.ASSIGNED,
            status_snapshot=Equipment.Status.USED,
            remarks="Issued for office use",
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))

        self.assertContains(response, "Assignment History")
        self.assertContains(response, self.employee.full_name)
        self.assertContains(response, "Issued for office use")

    def test_equipment_history_page_shows_assignment_timeline(self):
        assigned_at = timezone.make_aware(timezone.datetime(2026, 4, 15, 8, 30))
        returned_at = timezone.make_aware(timezone.datetime(2026, 4, 16, 17, 0))
        assignment = EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
            assigned_at=assigned_at,
            returned_at=returned_at,
            remarks="Returned after audit",
        )
        EquipmentHistoryLog.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.ASSIGNED,
            status_snapshot=Equipment.Status.USED,
            remarks="Returned after audit",
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:equipment-history", kwargs={"pk": self.equipment.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Equipment History")
        self.assertContains(response, self.employee.full_name)
        self.assertContains(response, "Returned after audit")
        self.assertContains(response, "USED")

    def test_admin_cannot_access_assignment_module(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("inventory:equipment-assign"))

        self.assertRedirects(response, reverse("accounts:manager-dashboard"))


class SupervisorEmployeeManagementTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superpeople",
            email="superpeople@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="adminpeople",
            email="adminpeople@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )

    def test_super_admin_can_create_supervisor(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:supervisor-create"),
            {
                "full_name": "Supervisor One",
                "employee_code": "SUP-100",
                "department": "Operations",
                "job_title": "Team Supervisor",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("inventory:supervisor-list"))
        self.assertTrue(Supervisor.objects.filter(employee_code="SUP-100").exists())

    def test_super_admin_can_create_employee_without_login(self):
        supervisor = Supervisor.objects.create(full_name="Supervisor One", employee_code="SUP-101")
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:employee-create"),
            {
                "full_name": "Employee One",
                "employee_code": "EMP-200",
                "department": "Operations",
                "team_name": "Warehouse",
                "job_title": "Clerk",
                "supervisor": supervisor.id,
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("inventory:employee-list"))
        self.assertTrue(Employee.objects.filter(employee_code="EMP-200", supervisor=supervisor).exists())
        self.assertFalse(User.objects.filter(username="EMP-200").exists())

    def test_super_admin_can_assign_employee_to_supervisor(self):
        supervisor = Supervisor.objects.create(full_name="Supervisor Two", employee_code="SUP-102")
        employee = Employee.objects.create(full_name="Employee Two", employee_code="EMP-201")
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:employee-assign-supervisor"),
            {
                "employee": employee.id,
                "supervisor": supervisor.id,
            },
        )
        employee.refresh_from_db()

        self.assertRedirects(response, reverse("inventory:employee-list"))
        self.assertEqual(employee.supervisor, supervisor)

    def test_employee_list_search_filters_by_name_id_and_supervisor(self):
        supervisor = Supervisor.objects.create(full_name="Target Supervisor", employee_code="SUP-103")
        Employee.objects.create(full_name="Alice Cruz", employee_code="EMP-300", supervisor=supervisor)
        Employee.objects.create(full_name="Brian Dela", employee_code="EMP-301")
        self.client.force_login(self.super_admin)

        by_name = self.client.get(reverse("inventory:employee-list"), {"q": "Alice"})
        by_id = self.client.get(reverse("inventory:employee-list"), {"q": "EMP-301"})
        by_supervisor = self.client.get(reverse("inventory:employee-list"), {"q": "Target Supervisor"})

        self.assertContains(by_name, "Alice Cruz")
        self.assertNotContains(by_name, "Brian Dela")
        self.assertContains(by_id, "Brian Dela")
        self.assertNotContains(by_id, "Alice Cruz")
        self.assertContains(by_supervisor, "Alice Cruz")
        self.assertNotContains(by_supervisor, "Brian Dela")

    def test_admin_cannot_access_supervisor_or_employee_management_pages(self):
        self.client.force_login(self.admin)

        supervisor_response = self.client.get(reverse("inventory:supervisor-list"))
        employee_response = self.client.get(reverse("inventory:employee-list"))

        self.assertRedirects(supervisor_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(employee_response, reverse("accounts:manager-dashboard"))
