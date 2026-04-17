from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        self.service = QueueService.objects.create(
            company=self.company,
            name="Registrar",
            code="R",
            max_queue_limit=2,
            current_queue_number=2,
        )
        self.cashier = QueueService.objects.create(
            company=self.company,
            name="Cashier",
            code="C",
            max_queue_limit=10,
            current_queue_number=3,
        )
        self.counter = QueueCounter.objects.create(
            company=self.company,
            name="Counter 1",
            assigned_service=self.service,
        )
        now = timezone.now()
        QueueTicket.objects.create(
            company=self.company,
            queue_number="R001",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.WAITING,
        )
        QueueTicket.objects.create(
            company=self.company,
            queue_number="R002",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.CALLED,
            called_at=now,
        )
        QueueTicket.objects.create(
            company=self.company,
            queue_number="C001",
            service=self.cashier,
            status=QueueTicket.Status.SKIPPED,
        )
        QueueTicket.objects.create(
            company=self.company,
            queue_number="C002",
            service=self.cashier,
            status=QueueTicket.Status.COMPLETED,
            called_at=now,
            completed_at=now,
        )

    def test_full_super_admin_can_open_queueing_dashboard(self):
        self.client.force_login(self.full_super_admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Queueing System")

    def test_queueing_dashboard_shows_shared_module_menu(self):
        self.client.force_login(self.full_super_admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Employee Tagging")
        self.assertContains(response, "Inventory")
        self.assertContains(response, "Queueing")
        self.assertContains(response, "Reports")
        self.assertContains(response, "Settings")

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

    def test_dashboard_shows_queue_analytics_and_edit_links_for_superadmin(self):
        self.client.force_login(self.full_super_admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Queued Today")
        self.assertContains(response, "4")
        self.assertContains(response, "Total Served Today")
        self.assertContains(response, "2")
        self.assertContains(response, "Total Pending")
        self.assertContains(response, "2")
        self.assertContains(response, "Total Skipped")
        self.assertContains(response, "1")
        self.assertContains(response, "Total Completed")
        self.assertContains(response, "1")
        self.assertContains(response, "Busiest Service Today")
        self.assertContains(response, "Registrar")
        self.assertContains(response, reverse("queueing:service-update", kwargs={"pk": self.service.pk}))
        self.assertContains(response, reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}))
        self.assertContains(response, "Services At Max Queue")

    def test_admin_dashboard_hides_superadmin_only_queue_setup_links(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("queueing:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("queueing:service-list"))
        self.assertNotContains(response, reverse("queueing:counter-list"))
        self.assertNotContains(response, reverse("queueing:setting-list"))
        self.assertNotContains(response, reverse("queueing:history-list"))


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
        self.super_admin = User.objects.create_user(
            username="queue-setup-root",
            password="password123",
            email="queue-setup-root@example.com",
            role=User.Role.SUPER_ADMIN,
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
            slug="registrar",
            refresh_interval_seconds=15,
        )
        self.screen.services.add(self.service)

    def test_admin_can_create_edit_and_deactivate_queue_service(self):
        self.client.force_login(self.super_admin)
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
                "show_in_ticket_generation": "on",
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
                "show_in_ticket_generation": "",
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
        self.assertFalse(self.service.show_in_ticket_generation)

    def test_service_create_blocks_duplicate_service_codes(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("queueing:service-create"),
            {
                "company": self.company.id,
                "name": "Cashier",
                "code": "R",
                "description": "Duplicate code",
                "is_active": "on",
                "max_queue_limit": 80,
                "current_queue_number": 0,
                "allow_priority": "",
                "show_in_ticket_generation": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A queue service with this code already exists for this tenant.")

    def test_admin_can_create_and_edit_counter_with_service_assignment(self):
        other_service = QueueService.objects.create(
            company=self.company,
            name="Pharmacy",
            code="P",
            max_queue_limit=30,
        )
        self.client.force_login(self.super_admin)
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
        self.client.force_login(self.super_admin)
        create_response = self.client.post(
            reverse("queueing:display-screen-create"),
            {
                "company": self.company.id,
                "name": "Lobby Screen",
                "slug": "cashier",
                "services": [self.service.id, second_service.id],
                "refresh_interval_seconds": 10,
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
                "slug": "main-screen-updated",
                "services": [second_service.id],
                "refresh_interval_seconds": 30,
            },
            follow=True,
        )
        self.screen.refresh_from_db()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(created_screen.services.count(), 2)
        self.assertEqual(created_screen.slug, "cashier")
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(self.screen.name, "Updated Main Screen")
        self.assertEqual(self.screen.slug, "main-screen-updated")
        self.assertEqual(self.screen.refresh_interval_seconds, 30)
        self.assertFalse(self.screen.is_active)
        self.assertEqual(list(self.screen.services.values_list("id", flat=True)), [second_service.id])

    def test_admin_can_create_and_edit_queue_system_settings(self):
        self.client.force_login(self.super_admin)
        create_response = self.client.post(
            reverse("queueing:setting-create"),
            {
                "company": self.company.id,
                "queue_reset_policy": QueueSystemSetting.QueueResetPolicy.DAILY,
                "default_max_queue_per_service": 120,
                "display_settings": '{"theme": "light"}',
                "announcement_settings": '{"voice": "on"}',
            },
            follow=True,
        )
        settings_record = QueueSystemSetting.objects.get(company=self.company)
        update_response = self.client.post(
            reverse("queueing:setting-update", kwargs={"pk": settings_record.pk}),
            {
                "company": self.company.id,
                "queue_reset_policy": QueueSystemSetting.QueueResetPolicy.MANUAL,
                "default_max_queue_per_service": 150,
                "display_settings": '{"theme": "dark"}',
                "announcement_settings": '{"voice": "off"}',
            },
            follow=True,
        )
        settings_record.refresh_from_db()

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(settings_record.queue_reset_policy, QueueSystemSetting.QueueResetPolicy.MANUAL)
        self.assertEqual(settings_record.default_max_queue_per_service, 150)
        self.assertEqual(settings_record.display_settings["theme"], "dark")

    def test_setup_lists_show_edit_buttons(self):
        self.client.force_login(self.super_admin)

        service_response = self.client.get(reverse("queueing:service-list"))
        counter_response = self.client.get(reverse("queueing:counter-list"))
        screen_response = self.client.get(reverse("queueing:display-screen-list"))

        self.assertContains(service_response, reverse("queueing:service-update", kwargs={"pk": self.service.pk}))
        self.assertContains(counter_response, reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}))
        self.assertContains(screen_response, reverse("queueing:display-screen-update", kwargs={"pk": self.screen.pk}))

    def test_admin_is_blocked_from_superadmin_only_queue_setup_pages(self):
        self.client.force_login(self.admin)

        service_response = self.client.get(reverse("queueing:service-list"))
        counter_response = self.client.get(reverse("queueing:counter-list"))
        screen_response = self.client.get(reverse("queueing:display-screen-list"))
        setting_response = self.client.get(reverse("queueing:setting-list"))
        history_response = self.client.get(reverse("queueing:history-list"))
        delete_response = self.client.post(reverse("queueing:service-delete", kwargs={"pk": self.service.pk}), follow=True)

        self.assertRedirects(service_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(counter_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(screen_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(setting_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(history_response, reverse("accounts:manager-dashboard"))
        self.assertRedirects(delete_response, reverse("accounts:manager-dashboard"))

    def test_superadmin_can_delete_unused_queue_service(self):
        removable_service = QueueService.objects.create(
            company=self.company,
            name="Unused Service",
            code="U",
            max_queue_limit=20,
        )
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("queueing:service-delete", kwargs={"pk": removable_service.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(QueueService.objects.filter(pk=removable_service.pk).exists())

    def test_superadmin_cannot_delete_service_with_related_records(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("queueing:service-delete", kwargs={"pk": self.service.pk}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(QueueService.objects.filter(pk=self.service.pk).exists())
        self.assertContains(response, "Queue service cannot be deleted while it is linked")

    def test_superadmin_dashboard_and_ticket_update_show_queue_settings_links(self):
        settings_record = QueueSystemSetting.objects.create(
            company=self.company,
            queue_reset_policy=QueueSystemSetting.QueueResetPolicy.DAILY,
            default_max_queue_per_service=100,
            display_settings={"theme": "light"},
            announcement_settings={"voice": "on"},
        )
        tenant_super_admin = User.objects.create_user(
            username="queue-tenant-root",
            password="password123",
            email="queue-tenant-root@example.com",
            role=User.Role.SUPER_ADMIN,
            company=self.company,
            can_access_queueing=True,
        )
        ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R020",
            service=self.service,
            assigned_counter=self.counter,
        )
        self.client.force_login(tenant_super_admin)

        dashboard_response = self.client.get(reverse("queueing:dashboard"))
        update_response = self.client.get(reverse("queueing:ticket-update", kwargs={"pk": ticket.pk}))

        self.assertContains(dashboard_response, reverse("queueing:setting-update", kwargs={"pk": settings_record.pk}))
        self.assertContains(update_response, reverse("queueing:setting-list"))
        self.assertContains(update_response, reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}))

    def test_display_screen_view_shows_current_and_recent_called_numbers(self):
        called_ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R010",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.CALLED,
            called_at=timezone.now(),
        )
        serving_ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R011",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.SERVING,
            called_at=timezone.now() + timezone.timedelta(minutes=1),
        )
        completed_ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R009",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.COMPLETED,
            called_at=timezone.now() - timezone.timedelta(minutes=2),
            completed_at=timezone.now() - timezone.timedelta(minutes=1),
        )

        response = self.client.get(reverse("queueing:display-screen-view", kwargs={"slug": self.screen.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Now Serving")
        self.assertContains(response, serving_ticket.queue_number)
        self.assertContains(response, called_ticket.queue_number)
        self.assertContains(response, completed_ticket.queue_number)
        self.assertContains(response, 'http-equiv="refresh" content="15"')

    def test_inactive_display_screen_is_not_publicly_accessible(self):
        self.screen.is_active = False
        self.screen.save(update_fields=["is_active"])

        response = self.client.get(reverse("queueing:display-screen-view", kwargs={"slug": self.screen.slug}))

        self.assertEqual(response.status_code, 404)

    def test_admin_can_generate_ticket_when_service_is_below_limit(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("queueing:ticket-create"),
            {
                "service": self.service.id,
                "is_priority": "on",
            },
            follow=True,
        )
        self.service.refresh_from_db()
        ticket = QueueTicket.objects.get(service=self.service, queue_number="R001")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Queue Ticket Generated")
        self.assertContains(response, "R001")
        self.assertEqual(self.service.current_queue_number, 1)
        self.assertTrue(ticket.is_priority)
        self.assertTrue(
            QueueHistoryLog.objects.filter(
                ticket=ticket,
                action=QueueHistoryLog.Action.CREATED,
            ).exists()
        )

    def test_admin_cannot_generate_ticket_when_service_limit_is_reached(self):
        self.service.current_queue_number = self.service.max_queue_limit
        self.service.save(update_fields=["current_queue_number"])

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("queueing:ticket-create"),
            {
                "service": self.service.id,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maximum queue limit reached for this service")
        self.assertFalse(QueueTicket.objects.filter(service=self.service, queue_number="R001").exists())

    def test_admin_cannot_generate_ticket_for_inactive_service(self):
        self.service.is_active = False
        self.service.save(update_fields=["is_active"])

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("queueing:ticket-create"),
            {
                "service": self.service.id,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(QueueTicket.objects.filter(service=self.service).exists())

    def test_ticket_generation_only_shows_enabled_services(self):
        QueueService.objects.create(
            company=self.company,
            name="Pharmacy",
            code="P",
            max_queue_limit=50,
            show_in_ticket_generation=False,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("queueing:ticket-create"))

        self.assertContains(response, "Registrar")
        self.assertNotContains(response, "Pharmacy")

    def test_success_page_shows_service_edit_button_for_full_super_admin(self):
        ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R001",
            service=self.service,
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("queueing:ticket-success", kwargs={"pk": ticket.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("queueing:service-update", kwargs={"pk": self.service.pk}))

    def test_success_page_hides_service_edit_button_for_admin(self):
        ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R001",
            service=self.service,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("queueing:ticket-success", kwargs={"pk": ticket.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Edit Service Settings")

    def test_full_super_admin_can_open_ticket_generation_page(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("queueing:ticket-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registrar")

    def test_operator_panel_can_call_next_mark_serving_mark_done_skip_and_recall(self):
        waiting_ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R002",
            service=self.service,
        )
        skipped_ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R003",
            service=self.service,
            status=QueueTicket.Status.SKIPPED,
        )
        self.client.force_login(self.admin)

        call_next_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "call_next",
                "service": self.service.id,
                "counter": self.counter.id,
            },
            follow=True,
        )
        waiting_ticket.refresh_from_db()
        self.assertEqual(call_next_response.status_code, 200)
        self.assertEqual(waiting_ticket.status, QueueTicket.Status.CALLED)
        self.assertEqual(waiting_ticket.assigned_counter, self.counter)

        serving_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "mark_serving",
                "ticket_id": waiting_ticket.id,
                "counter": self.counter.id,
            },
            follow=True,
        )
        waiting_ticket.refresh_from_db()
        self.assertEqual(serving_response.status_code, 200)
        self.assertEqual(waiting_ticket.status, QueueTicket.Status.SERVING)

        done_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "mark_done",
                "ticket_id": waiting_ticket.id,
            },
            follow=True,
        )
        waiting_ticket.refresh_from_db()
        self.assertEqual(done_response.status_code, 200)
        self.assertEqual(waiting_ticket.status, QueueTicket.Status.COMPLETED)
        self.assertIsNotNone(waiting_ticket.completed_at)

        recall_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "recall",
                "ticket_id": skipped_ticket.id,
                "counter": self.counter.id,
            },
            follow=True,
        )
        skipped_ticket.refresh_from_db()

        self.assertEqual(recall_response.status_code, 200)
        self.assertEqual(skipped_ticket.status, QueueTicket.Status.CALLED)
        self.assertEqual(skipped_ticket.assigned_counter, self.counter)

    def test_operator_panel_can_call_specific_and_skip_ticket(self):
        ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R004",
            service=self.service,
        )
        self.client.force_login(self.admin)

        call_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "call_specific",
                "ticket_id": ticket.id,
                "counter": self.counter.id,
            },
            follow=True,
        )
        ticket.refresh_from_db()

        skip_response = self.client.post(
            reverse("queueing:operator-panel"),
            {
                "queue_action": "skip",
                "ticket_id": ticket.id,
            },
            follow=True,
        )
        ticket.refresh_from_db()

        self.assertEqual(call_response.status_code, 200)
        self.assertEqual(ticket.assigned_counter, self.counter)
        self.assertEqual(skip_response.status_code, 200)
        self.assertEqual(ticket.status, QueueTicket.Status.SKIPPED)

    def test_admin_can_manually_update_ticket_service_status_and_counter(self):
        other_service = QueueService.objects.create(
            company=self.company,
            name="Cashier",
            code="C",
            max_queue_limit=80,
        )
        other_counter = QueueCounter.objects.create(
            company=self.company,
            name="Counter 2",
            assigned_service=other_service,
        )
        ticket = QueueTicket.objects.create(
            company=self.company,
            queue_number="R005",
            service=self.service,
            assigned_counter=self.counter,
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("queueing:ticket-update", kwargs={"pk": ticket.pk}),
            {
                "service": other_service.id,
                "status": QueueTicket.Status.SERVING,
                "assigned_counter": other_counter.id,
                "is_priority": "on",
            },
            follow=True,
        )
        ticket.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ticket.service, other_service)
        self.assertEqual(ticket.assigned_counter, other_counter)
        self.assertEqual(ticket.status, QueueTicket.Status.SERVING)
        self.assertTrue(ticket.is_priority)
        self.assertTrue(
            QueueHistoryLog.objects.filter(ticket=ticket, action=QueueHistoryLog.Action.REASSIGNED).exists()
        )
        self.assertTrue(
            QueueHistoryLog.objects.filter(ticket=ticket, action=QueueHistoryLog.Action.MANUAL_EDITED).exists()
        )

    def test_service_and_counter_updates_create_history_logs(self):
        self.client.force_login(self.super_admin)

        service_response = self.client.post(
            reverse("queueing:service-update", kwargs={"pk": self.service.pk}),
            {
                "company": self.company.id,
                "name": "Enrollment",
                "code": "R",
                "description": "Updated name",
                "is_active": "on",
                "max_queue_limit": 80,
                "current_queue_number": 2,
                "allow_priority": "on",
                "show_in_ticket_generation": "on",
            },
            follow=True,
        )
        counter_response = self.client.post(
            reverse("queueing:counter-update", kwargs={"pk": self.counter.pk}),
            {
                "company": self.company.id,
                "name": "Counter A",
                "assigned_service": self.service.id,
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(service_response.status_code, 200)
        self.assertEqual(counter_response.status_code, 200)
        self.assertTrue(
            QueueHistoryLog.objects.filter(
                company=self.company,
                action=QueueHistoryLog.Action.SERVICE_UPDATED,
                service=self.service,
            ).exists()
        )
        self.assertTrue(
            QueueHistoryLog.objects.filter(
                company=self.company,
                action=QueueHistoryLog.Action.COUNTER_UPDATED,
                counter=self.counter,
            ).exists()
        )

    def test_history_page_filters_by_date_service_status_and_counter(self):
        other_service = QueueService.objects.create(
            company=self.company,
            name="Cashier",
            code="C",
            max_queue_limit=40,
        )
        other_counter = QueueCounter.objects.create(
            company=self.company,
            name="Counter 2",
            assigned_service=other_service,
        )
        ticket_one = QueueTicket.objects.create(
            company=self.company,
            queue_number="R010",
            service=self.service,
            assigned_counter=self.counter,
            status=QueueTicket.Status.CALLED,
            called_at=timezone.now(),
        )
        ticket_two = QueueTicket.objects.create(
            company=self.company,
            queue_number="C001",
            service=other_service,
            assigned_counter=other_counter,
            status=QueueTicket.Status.SKIPPED,
        )
        log_one = QueueHistoryLog.objects.create(
            company=self.company,
            ticket=ticket_one,
            service=self.service,
            counter=self.counter,
            actor=self.admin,
            action=QueueHistoryLog.Action.CALLED,
            status_snapshot=QueueTicket.Status.CALLED,
            notes="Called from operator panel.",
        )
        QueueHistoryLog.objects.create(
            company=self.company,
            ticket=ticket_two,
            service=other_service,
            counter=other_counter,
            actor=self.admin,
            action=QueueHistoryLog.Action.SKIPPED,
            status_snapshot=QueueTicket.Status.SKIPPED,
            notes="Skipped in queue.",
        )

        self.client.force_login(self.super_admin)
        response = self.client.get(
            reverse("queueing:history-list"),
            {
                "date": timezone.localdate().isoformat(),
                "service": str(self.service.id),
                "status": QueueTicket.Status.CALLED,
                "counter": str(self.counter.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, log_one.ticket.queue_number)
        self.assertNotContains(response, ticket_two.queue_number)
        self.assertContains(response, "Called")


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
            show_in_ticket_generation=True,
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
        screen.slug = "main-lobby"
        screen.refresh_interval_seconds = 20
        screen.save()
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
            status_snapshot=QueueTicket.Status.WAITING,
            notes="Ticket created from front desk.",
        )

        self.assertEqual(self.service.name, "Registrar")
        self.assertEqual(self.service.code, "R")
        self.assertEqual(self.service.max_queue_limit, 250)
        self.assertTrue(self.service.allow_priority)
        self.assertTrue(self.service.show_in_ticket_generation)
        self.assertEqual(self.counter.assigned_service, self.service)
        self.assertEqual(self.ticket.status, QueueTicket.Status.WAITING)
        self.assertTrue(self.ticket.is_priority)
        self.assertEqual(history.actor, self.super_admin)
        self.assertEqual(history.status_snapshot, QueueTicket.Status.WAITING)
        self.assertEqual(screen.services.first(), self.service)
        self.assertEqual(screen.slug, "main-lobby")
        self.assertEqual(screen.refresh_interval_seconds, 20)
        self.assertEqual(settings_record.default_max_queue_per_service, 300)

    def test_platform_super_admin_can_open_queue_service_admin_add_page(self):
        self.client.force_login(self.super_admin)
        response = self.client.get("/admin/queueing/queueservice/add/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name")
        self.assertContains(response, "code")
        self.assertContains(response, "max_queue_limit")
