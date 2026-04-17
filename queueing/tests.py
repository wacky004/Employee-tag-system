from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Company
from .models import (
    QueueCounter,
    QueueDisplayScreen,
    QueueHistoryLog,
    QueueService,
    QueueSystemSetting,
    QueueTicket,
)

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


class QueueingSetupPageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Health Center",
            code="HEALTH",
            can_use_queueing=True,
        )
        self.admin = User.objects.create_user(
            username="queue-setup-admin",
            password="password123",
            email="queue-setup-admin@example.com",
            role=User.Role.ADMIN,
            company=self.company,
            can_access_queueing=True,
        )
        self.service = QueueService.objects.create(
            company=self.company,
            name="Registrar",
            code="R",
            max_queue_limit=50,
        )
        self.counter = QueueCounter.objects.create(
            company=self.company,
            name="Counter 1",
            assigned_service=self.service,
        )
        self.screen = QueueDisplayScreen.objects.create(
            company=self.company,
            name="Main Screen",
        )
        self.screen.services.add(self.service)

    def test_admin_can_create_edit_and_deactivate_queue_service(self):
        self.client.force_login(self.admin)
        create_response = self.client.post(
            reverse("queueing:service-create"),
            {
                "company": self.company.id,
                "name": "Cashier",
                "code": "C",
                "description": "Payment counter",
                "is_active": "on",
                "max_queue_limit": 50,
                "current_queue_number": 0,
                "allow_priority": "on",
            },
            follow=True,
        )

        cashier = QueueService.objects.get(company=self.company, code="C")
        update_response = self.client.post(
            reverse("queueing:service-update", kwargs={"pk": self.service.pk}),
            {
                "company": self.company.id,
                "name": "Enrollment",
                "code": "R",
                "description": "Updated service name",
                "max_queue_limit": 100,
                "current_queue_number": 12,
                "allow_priority": "",
            },
            follow=True,
        )
        self.service.refresh_from_db()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(cashier.name, "Cashier")
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(self.service.name, "Enrollment")
        self.assertEqual(self.service.max_queue_limit, 100)
        self.assertFalse(self.service.is_active)

    def test_admin_can_create_and_edit_counter_with_service_assignment(self):
        other_service = QueueService.objects.create(
            company=self.company,
            name="Pharmacy",
            code="P",
            max_queue_limit=30,
        )
        self.client.force_login(self.admin)
        create_response = self.client.post(
            reverse("queueing:counter-create"),
            {
                "company": self.company.id,
                "name": "Counter 2",
                "assigned_service": other_service.id,
                "is_active": "on",
            },
            follow=True,
        )

        created_counter = QueueCounter.objects.get(company=self.company, name="Counter 2")
        update_response = self.client.post(
            reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}),
            {
                "company": self.company.id,
                "name": "Front Desk Counter",
                "assigned_service": other_service.id,
                "is_active": "",
            },
            follow=True,
        )
        self.counter.refresh_from_db()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(created_counter.assigned_service, other_service)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(self.counter.name, "Front Desk Counter")
        self.assertEqual(self.counter.assigned_service, other_service)
        self.assertFalse(self.counter.is_active)

    def test_admin_can_create_and_edit_display_screen(self):
        second_service = QueueService.objects.create(
            company=self.company,
            name="Cashier",
            code="C",
            max_queue_limit=40,
        )
        self.client.force_login(self.admin)
        create_response = self.client.post(
            reverse("queueing:display-screen-create"),
            {
                "company": self.company.id,
                "name": "Lobby Screen",
                "services": [self.service.id, second_service.id],
                "is_active": "on",
            },
            follow=True,
        )

        created_screen = QueueDisplayScreen.objects.get(company=self.company, name="Lobby Screen")
        update_response = self.client.post(
            reverse("queueing:display-screen-update", kwargs={"pk": self.screen.pk}),
            {
                "company": self.company.id,
                "name": "Updated Main Screen",
                "services": [second_service.id],
            },
            follow=True,
        )
        self.screen.refresh_from_db()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(created_screen.services.count(), 2)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(self.screen.name, "Updated Main Screen")
        self.assertFalse(self.screen.is_active)
        self.assertEqual(list(self.screen.services.values_list("id", flat=True)), [second_service.id])

    def test_setup_lists_show_edit_buttons(self):
        self.client.force_login(self.admin)

        service_response = self.client.get(reverse("queueing:service-list"))
        counter_response = self.client.get(reverse("queueing:counter-list"))
        screen_response = self.client.get(reverse("queueing:display-screen-list"))

        self.assertContains(service_response, reverse("queueing:service-update", kwargs={"pk": self.service.pk}))
        self.assertContains(counter_response, reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}))
        self.assertContains(screen_response, reverse("queueing:display-screen-update", kwargs={"pk": self.screen.pk}))


class QueueingModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Campus Services",
            code="CAMPUS",
            can_use_queueing=True,
        )
        self.super_admin = User.objects.create_user(
            username="queue-super",
            password="password123",
            email="queue-super@example.com",
            role=User.Role.SUPER_ADMIN,
        )
        self.service = QueueService.objects.create(
            company=self.company,
            name="Registrar",
            code="R",
            description="Handles registration requests.",
            max_queue_limit=250,
            current_queue_number=18,
            allow_priority=True,
        )
        self.counter = QueueCounter.objects.create(
            company=self.company,
            name="Counter 1",
            assigned_service=self.service,
        )
        self.ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R-019",
            service=self.service,
            assigned_counter=self.counter,
            is_priority=True,
        )

    def test_core_queueing_models_store_required_fields(self):
        screen = QueueDisplayScreen.objects.create(company=self.company, name="Main Lobby")
        screen.services.add(self.service)
        settings_record = QueueSystemSetting.objects.create(
            company=self.company,
            queue_reset_policy=QueueSystemSetting.QueueResetPolicy.DAILY,
            display_settings={"theme": "light"},
            default_max_queue_per_service=300,
            announcement_settings={"voice": "enabled"},
        )
        history = QueueHistoryLog.objects.create(
            company=self.company,
            ticket=self.ticket,
            service=self.service,
            counter=self.counter,
            actor=self.super_admin,
            action=QueueHistoryLog.Action.CREATED,
            notes="Ticket created from front desk.",
        )

        self.assertEqual(self.service.name, "Registrar")
        self.assertEqual(self.service.code, "R")
        self.assertEqual(self.service.max_queue_limit, 250)
        self.assertTrue(self.service.allow_priority)
        self.assertEqual(self.counter.assigned_service, self.service)
        self.assertEqual(self.ticket.status, QueueTicket.Status.WAITING)
        self.assertTrue(self.ticket.is_priority)
        self.assertEqual(history.actor, self.super_admin)
        self.assertEqual(screen.services.first(), self.service)
        self.assertEqual(settings_record.default_max_queue_per_service, 300)

    def test_platform_super_admin_can_open_queue_service_admin_add_page(self):
        self.client.force_login(self.super_admin)
        response = self.client.get("/admin/queueing/queueservice/add/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name")
        self.assertContains(response, "code")
        self.assertContains(response, "max_queue_limit")
