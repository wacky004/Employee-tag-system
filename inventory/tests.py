from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Employee,
    Equipment,
    EquipmentAssignment,
    EquipmentCategory,
    EquipmentHistoryLog,
    InventoryAuditLog,
    Supervisor,
)

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

    def test_inventory_summary_dashboard_shows_totals(self):
        user = User.objects.create_user(
            username="summarysuper",
            email="summarysuper@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        supervisor = Supervisor.objects.create(full_name="Summary Supervisor", employee_code="SUP-500")
        employee = Employee.objects.create(full_name="Summary Employee", employee_code="EMP-500", supervisor=supervisor)
        assigned_equipment = Equipment.objects.create(
            asset_code="EQ-500",
            name="Laptop Summary",
            status=Equipment.Status.BRANDNEW,
            current_employee=employee,
        )
        Equipment.objects.create(
            asset_code="EQ-501",
            name="Headset Summary",
            status=Equipment.Status.DEFECTIVE,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("inventory:summary"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Summary Dashboard")
        self.assertContains(response, "2")
        self.assertContains(response, "1")
        self.assertContains(response, "Brand New")
        self.assertContains(response, "Defective")


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

    def test_super_admin_can_update_equipment_without_changing_assignment_history(self):
        user = User.objects.create_user(
            username="superupdateequipment",
            email="superupdateequipment@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        category = EquipmentCategory.objects.create(name="Laptop", code="LAPTOP")
        employee = Employee.objects.create(full_name="Assigned Employee", employee_code="EMP-550")
        equipment = Equipment.objects.create(
            asset_code="COMP-0002",
            name="Office Laptop",
            category=category,
            status=Equipment.Status.UNUSED,
            current_employee=employee,
        )
        assignment = EquipmentAssignment.objects.create(
            equipment=equipment,
            employee=employee,
            assigned_by=user,
            remarks="Original assignment",
        )
        EquipmentHistoryLog.objects.create(
            equipment=equipment,
            employee=employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.ASSIGNED,
            status_snapshot=Equipment.Status.UNUSED,
            remarks="Original assignment",
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("inventory:equipment-update", kwargs={"pk": equipment.pk}),
            {
                "name": "Office Laptop Updated",
                "category": category.id,
                "brand": "Dell",
                "model": "Latitude 7450",
                "serial_number": "SN-0002",
                "asset_code": "COMP-0002",
                "status": Equipment.Status.DEFECTIVE,
                "notes": "Status updated during inspection",
            },
        )
        equipment.refresh_from_db()
        assignment.refresh_from_db()

        self.assertRedirects(response, reverse("inventory:equipment-detail", kwargs={"pk": equipment.pk}))
        self.assertEqual(equipment.name, "Office Laptop Updated")
        self.assertEqual(equipment.status, Equipment.Status.DEFECTIVE)
        self.assertEqual(equipment.current_employee, employee)
        self.assertIsNone(assignment.returned_at)
        self.assertEqual(assignment.remarks, "Original assignment")


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

    def test_returned_equipment_becomes_available_for_reassignment(self):
        assignment = EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
        )
        self.equipment.current_employee = self.employee
        self.equipment.save(update_fields=["current_employee"])

        self.client.force_login(self.super_admin)
        return_response = self.client.post(
            reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}),
            {
                "return-returned_at": "2026-04-16T09:30",
                "return-notes": "Returned and ready for reassignment",
            },
        )

        new_employee = Employee.objects.create(full_name="Replacement Employee", employee_code="EMP-902")
        assign_response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": self.equipment.id,
                "employee": new_employee.id,
                "assigned_at": "2026-04-16T11:00",
                "notes": "Reassigned after return",
            },
        )
        assignment.refresh_from_db()
        self.equipment.refresh_from_db()

        self.assertRedirects(return_response, reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))
        self.assertRedirects(assign_response, reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}))
        self.assertIsNotNone(assignment.returned_at)
        self.assertEqual(self.equipment.current_employee, new_employee)

    def test_cannot_return_equipment_twice(self):
        assignment = EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
            returned_at=timezone.make_aware(timezone.datetime(2026, 4, 16, 9, 30)),
        )
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:equipment-detail", kwargs={"pk": self.equipment.pk}),
            {
                "return-returned_at": "2026-04-16T10:00",
                "return-notes": "Second return attempt",
            },
            follow=True,
        )
        assignment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already been returned")
        self.assertEqual(
            assignment.returned_at,
            timezone.make_aware(timezone.datetime(2026, 4, 16, 9, 30)),
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

    def test_super_admin_can_update_supervisor(self):
        supervisor = Supervisor.objects.create(full_name="Supervisor Two", employee_code="SUP-102")

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:supervisor-update", kwargs={"pk": supervisor.pk}),
            {
                "full_name": "Supervisor Two Updated",
                "employee_code": "SUP-102",
                "department": "Operations",
                "job_title": "Area Supervisor",
                "is_active": "on",
            },
        )
        supervisor.refresh_from_db()

        self.assertRedirects(response, reverse("inventory:supervisor-list"))
        self.assertEqual(supervisor.full_name, "Supervisor Two Updated")
        self.assertEqual(supervisor.job_title, "Area Supervisor")

    def test_super_admin_can_update_employee(self):
        supervisor = Supervisor.objects.create(full_name="Supervisor Three", employee_code="SUP-103")
        employee = Employee.objects.create(full_name="Employee Three", employee_code="EMP-202")

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:employee-update", kwargs={"pk": employee.pk}),
            {
                "full_name": "Employee Three Updated",
                "employee_code": "EMP-202",
                "department": "Operations",
                "team_name": "Warehouse",
                "job_title": "Lead Clerk",
                "supervisor": supervisor.id,
                "is_active": "on",
            },
        )
        employee.refresh_from_db()

        self.assertRedirects(response, reverse("inventory:employee-detail", kwargs={"pk": employee.pk}))
        self.assertEqual(employee.full_name, "Employee Three Updated")
        self.assertEqual(employee.supervisor, supervisor)
        self.assertEqual(employee.job_title, "Lead Clerk")

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
        supervisor_update_response = self.client.get(
            reverse("inventory:supervisor-update", kwargs={"pk": Supervisor.objects.create(full_name="Locked", employee_code="SUP-104").pk})
        )
        employee_update_response = self.client.get(
            reverse("inventory:employee-update", kwargs={"pk": Employee.objects.create(full_name="Locked Employee", employee_code="EMP-203").pk})
        )

        self.assertRedirects(supervisor_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(employee_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(supervisor_update_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(employee_update_response, reverse("accounts:manager-dashboard"))


class EmployeeSearchModuleTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="supersearch",
            email="supersearch@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.supervisor = Supervisor.objects.create(full_name="Search Supervisor", employee_code="SUP-700")
        self.employee = Employee.objects.create(
            full_name="Maria Santos",
            employee_code="EMP-700",
            supervisor=self.supervisor,
            department="Operations",
            team_name="Warehouse",
            job_title="Storekeeper",
        )
        self.equipment = Equipment.objects.create(
            asset_code="EQ-700",
            name="Laptop Search",
            status=Equipment.Status.USED,
            current_employee=self.employee,
        )
        EquipmentAssignment.objects.create(
            equipment=self.equipment,
            employee=self.employee,
            assigned_by=self.super_admin,
            remarks="Issued for inventory work",
        )

    def test_search_page_filters_by_name_id_and_supervisor(self):
        self.client.force_login(self.super_admin)

        by_name = self.client.get(reverse("inventory:employee-search"), {"q": "Maria"})
        by_id = self.client.get(reverse("inventory:employee-search"), {"q": "EMP-700"})
        by_supervisor = self.client.get(reverse("inventory:employee-search"), {"q": "Search Supervisor"})

        self.assertContains(by_name, "Maria Santos")
        self.assertContains(by_id, "Maria Santos")
        self.assertContains(by_supervisor, "Maria Santos")
        self.assertContains(by_name, "Laptop Search")
        self.assertContains(by_name, "Used")

    def test_clicking_employee_opens_detail_page(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:employee-detail", kwargs={"pk": self.employee.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maria Santos")
        self.assertContains(response, "Search Supervisor")
        self.assertContains(response, "Laptop Search")
        self.assertContains(response, "Issued for inventory work")

    def test_employee_detail_shows_return_action_for_current_equipment(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:employee-detail", kwargs={"pk": self.employee.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mark as Returned")
        self.assertContains(response, "Open equipment detail")

    def test_super_admin_can_return_equipment_from_employee_detail(self):
        self.equipment.last_assigned_at = timezone.make_aware(timezone.datetime(2026, 4, 15, 9, 0))
        self.equipment.save(update_fields=["last_assigned_at"])

        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("inventory:employee-detail", kwargs={"pk": self.employee.pk}),
            {
                "equipment_id": self.equipment.id,
                "return-{}".format(self.equipment.id) + "-returned_at": "2026-04-16T14:00",
                "return-{}".format(self.equipment.id) + "-notes": "Returned from employee detail",
            },
        )
        self.equipment.refresh_from_db()
        assignment = EquipmentAssignment.objects.get(equipment=self.equipment, employee=self.employee)

        self.assertRedirects(response, reverse("inventory:employee-detail", kwargs={"pk": self.employee.pk}))
        self.assertIsNone(self.equipment.current_employee)
        self.assertIsNotNone(assignment.returned_at)
        self.assertTrue(
            EquipmentHistoryLog.objects.filter(
                equipment=self.equipment,
                action=EquipmentHistoryLog.Action.RETURNED,
                remarks="Returned from employee detail",
            ).exists()
        )


class InventoryAuditLogTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superaudit",
            email="superaudit@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="adminaudit",
            email="adminaudit@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )

    def test_super_admin_can_view_audit_log_page(self):
        InventoryAuditLog.objects.create(
            action=InventoryAuditLog.Action.SUPERVISOR_CREATED,
            actor=self.super_admin,
            target_type="supervisor",
            target_id=1,
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:audit-log-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Log")
        self.assertContains(response, "Supervisor Created")

    def test_admin_cannot_access_audit_log_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("inventory:audit-log-list"))

        self.assertRedirects(response, reverse("accounts:manager-dashboard"))

    def test_creating_supervisor_employee_and_equipment_writes_audit_logs(self):
        self.client.force_login(self.super_admin)

        supervisor_response = self.client.post(
            reverse("inventory:supervisor-create"),
            {
                "full_name": "Audit Supervisor",
                "employee_code": "SUP-900",
                "department": "Operations",
                "job_title": "Supervisor",
                "is_active": "on",
            },
        )
        supervisor = Supervisor.objects.get(employee_code="SUP-900")

        employee_response = self.client.post(
            reverse("inventory:employee-create"),
            {
                "full_name": "Audit Employee",
                "employee_code": "EMP-900",
                "department": "Operations",
                "team_name": "Warehouse",
                "job_title": "Clerk",
                "supervisor": supervisor.id,
                "is_active": "on",
            },
        )

        equipment_response = self.client.post(
            reverse("inventory:equipment-create"),
            {
                "name": "Audit Laptop",
                "category": "",
                "brand": "Dell",
                "model": "Latitude",
                "serial_number": "AUDIT-001",
                "asset_code": "EQ-AUDIT-001",
                "status": Equipment.Status.BRANDNEW,
                "notes": "Created for audit testing",
            },
        )
        equipment = Equipment.objects.get(asset_code="EQ-AUDIT-001")

        self.assertRedirects(supervisor_response, reverse("inventory:supervisor-list"))
        self.assertRedirects(employee_response, reverse("inventory:employee-list"))
        self.assertRedirects(equipment_response, reverse("inventory:equipment-create"))
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.SUPERVISOR_CREATED,
                target_type="supervisor",
                target_id=supervisor.id,
            ).exists()
        )
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.EMPLOYEE_CREATED,
                target_type="employee",
                target_id=Employee.objects.get(employee_code="EMP-900").id,
            ).exists()
        )
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.EQUIPMENT_CREATED,
                target_type="equipment",
                target_id=equipment.id,
            ).exists()
        )

    def test_edit_assign_and_return_equipment_write_audit_logs(self):
        employee = Employee.objects.create(full_name="Audit Employee", employee_code="EMP-901")
        equipment = Equipment.objects.create(
            asset_code="EQ-AUDIT-002",
            name="Audit Monitor",
            status=Equipment.Status.UNUSED,
        )
        self.client.force_login(self.super_admin)

        update_response = self.client.post(
            reverse("inventory:equipment-update", kwargs={"pk": equipment.pk}),
            {
                "name": "Audit Monitor Updated",
                "category": "",
                "brand": "HP",
                "model": "M24",
                "serial_number": "AUDIT-002",
                "asset_code": "EQ-AUDIT-002",
                "status": Equipment.Status.TO_BE_CHECKED,
                "notes": "Updated during audit",
            },
        )
        assign_response = self.client.post(
            reverse("inventory:equipment-assign"),
            {
                "equipment": equipment.id,
                "employee": employee.id,
                "assigned_at": "2026-04-15T09:00",
                "notes": "Assigned during audit",
            },
        )
        return_response = self.client.post(
            reverse("inventory:equipment-detail", kwargs={"pk": equipment.pk}),
            {
                "return-returned_at": "2026-04-16T09:00",
                "return-notes": "Returned during audit",
            },
        )

        self.assertRedirects(update_response, reverse("inventory:equipment-detail", kwargs={"pk": equipment.pk}))
        self.assertRedirects(assign_response, reverse("inventory:equipment-detail", kwargs={"pk": equipment.pk}))
        self.assertRedirects(return_response, reverse("inventory:equipment-detail", kwargs={"pk": equipment.pk}))
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.EQUIPMENT_UPDATED,
                target_type="equipment",
                target_id=equipment.id,
            ).exists()
        )
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.EQUIPMENT_ASSIGNED,
                target_type="equipment",
                target_id=equipment.id,
            ).exists()
        )
        self.assertTrue(
            InventoryAuditLog.objects.filter(
                action=InventoryAuditLog.Action.EQUIPMENT_RETURNED,
                target_type="equipment",
                target_id=equipment.id,
                notes="Returned during audit",
            ).exists()
        )


class EquipmentReportingTests(TestCase):
    def setUp(self):
        self.super_admin = User.objects.create_user(
            username="superreports",
            email="superreports@example.com",
            password="pass12345",
            role=User.Role.SUPER_ADMIN,
        )
        self.admin = User.objects.create_user(
            username="adminreports",
            email="adminreports@example.com",
            password="pass12345",
            role=User.Role.ADMIN,
        )
        self.supervisor_one = Supervisor.objects.create(full_name="Supervisor One", employee_code="SUP-801")
        self.supervisor_two = Supervisor.objects.create(full_name="Supervisor Two", employee_code="SUP-802")
        self.employee_one = Employee.objects.create(
            full_name="Employee One",
            employee_code="EMP-801",
            supervisor=self.supervisor_one,
        )
        self.employee_two = Employee.objects.create(
            full_name="Employee Two",
            employee_code="EMP-802",
            supervisor=self.supervisor_two,
        )
        self.laptop_category = EquipmentCategory.objects.create(name="Laptop", code="LAPTOP")
        self.monitor_category = EquipmentCategory.objects.create(name="Monitor", code="MONITOR")
        self.defective_equipment = Equipment.objects.create(
            asset_code="EQ-801",
            name="Defective Laptop",
            category=self.laptop_category,
            brand="Dell",
            status=Equipment.Status.DEFECTIVE,
            current_employee=self.employee_one,
        )
        self.unused_equipment = Equipment.objects.create(
            asset_code="EQ-802",
            name="Unused Monitor",
            category=self.monitor_category,
            brand="HP",
            status=Equipment.Status.UNUSED,
        )
        self.assigned_equipment = Equipment.objects.create(
            asset_code="EQ-803",
            name="Assigned Laptop",
            category=self.laptop_category,
            brand="Lenovo",
            status=Equipment.Status.USED,
            current_employee=self.employee_two,
        )

    def test_equipment_report_filters_by_status_category_brand_supervisor_and_assignment(self):
        self.client.force_login(self.super_admin)

        by_status = self.client.get(reverse("inventory:equipment-report-list"), {"status": Equipment.Status.DEFECTIVE})
        by_category = self.client.get(reverse("inventory:equipment-report-list"), {"category": str(self.monitor_category.id)})
        by_brand = self.client.get(reverse("inventory:equipment-report-list"), {"brand": "Lenovo"})
        by_supervisor = self.client.get(reverse("inventory:equipment-report-list"), {"supervisor": str(self.supervisor_one.id)})
        by_assignment = self.client.get(reverse("inventory:equipment-report-list"), {"assignment": "unassigned"})

        self.assertContains(by_status, "Defective Laptop")
        self.assertNotContains(by_status, "Unused Monitor")
        self.assertContains(by_category, "Unused Monitor")
        self.assertNotContains(by_category, "Defective Laptop")
        self.assertContains(by_brand, "Assigned Laptop")
        self.assertNotContains(by_brand, "Defective Laptop")
        self.assertContains(by_supervisor, "Defective Laptop")
        self.assertNotContains(by_supervisor, "Assigned Laptop")
        self.assertContains(by_assignment, "Unused Monitor")
        self.assertNotContains(by_assignment, "Assigned Laptop")

    def test_defective_equipment_report_shows_only_defective_items(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:defective-equipment-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Defective Equipment")
        self.assertContains(response, "Defective Laptop")
        self.assertNotContains(response, "Unused Monitor")

    def test_unused_equipment_report_shows_only_unused_items(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:unused-equipment-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unused Equipment")
        self.assertContains(response, "Unused Monitor")
        self.assertNotContains(response, "Assigned Laptop")

    def test_assigned_equipment_report_shows_only_assigned_items(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:assigned-equipment-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assigned Equipment")
        self.assertContains(response, "Defective Laptop")
        self.assertContains(response, "Assigned Laptop")
        self.assertNotContains(response, "Unused Monitor")

    def test_unassigned_equipment_report_shows_only_unassigned_items(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("inventory:unassigned-equipment-report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unassigned Equipment")
        self.assertContains(response, "Unused Monitor")
        self.assertNotContains(response, "Defective Laptop")

    def test_admin_can_access_equipment_reports(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("inventory:equipment-report-list"))

        self.assertEqual(response.status_code, 200)
