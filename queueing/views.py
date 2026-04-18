from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, F, Q
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    QueueCallNextForm,
    QueueCounterForm,
    QueueDisplayScreenForm,
    QueueServiceForm,
    QueueSystemSettingForm,
    QueueTicketGenerationForm,
    QueueTicketUpdateForm,
)
from .models import QueueCounter, QueueDisplayScreen, QueueHistoryLog, QueueService, QueueSystemSetting, QueueTicket

User = get_user_model()


def _dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class QueueingAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_queueing_module_access()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(_dashboard_url(self.request.user))
        return super().handle_no_permission()


class QueueingSetupMixin(QueueingAccessMixin):
    def _company_queryset(self, queryset):
        if self.request.user.company_id:
            return queryset.filter(company=self.request.user.company)
        return queryset

    def _form_kwargs(self):
        return {
            "company": self.request.user.company,
            "can_manage_companies": self.request.user.can_manage_companies(),
        }


class QueueingSuperAdminAccessMixin(QueueingSetupMixin):
    def test_func(self):
        return super().test_func() and self.request.user.role == User.Role.SUPER_ADMIN


def _log_queue_action(*, actor, action, ticket=None, notes="", counter=None, service=None, company=None, status_snapshot=""):
    if ticket is not None:
        company = company or ticket.company
        service = service or ticket.service
        if counter is None:
            counter = ticket.assigned_counter
        if not status_snapshot:
            status_snapshot = ticket.status
    QueueHistoryLog.objects.create(
        company=company,
        ticket=ticket,
        service=service,
        counter=counter,
        actor=actor,
        action=action,
        status_snapshot=status_snapshot,
        notes=notes,
    )


def _summarize_changes(field_labels, previous_object, current_object):
    changes = []
    for field_name, label in field_labels:
        previous_value = getattr(previous_object, field_name)
        current_value = getattr(current_object, field_name)
        if previous_value != current_value:
            changes.append(f"{label}: {previous_value or '-'} -> {current_value or '-'}")
    return "; ".join(changes) if changes else "Updated from the queue setup page."


class QueueingDashboardView(QueueingAccessMixin, TemplateView):
    template_name = "queueing/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        services = QueueService.objects.all()
        counters = QueueCounter.objects.all()
        tickets = QueueTicket.objects.all()
        screens = QueueDisplayScreen.objects.all()
        settings_record = QueueSystemSetting.objects.none()

        if company:
            services = services.filter(company=company)
            counters = counters.filter(company=company)
            tickets = tickets.filter(company=company)
            screens = screens.filter(company=company)
            settings_record = QueueSystemSetting.objects.filter(company=company)

        today = timezone.localdate()
        pending_statuses = [
            QueueTicket.Status.WAITING,
            QueueTicket.Status.CALLED,
            QueueTicket.Status.SERVING,
        ]
        service_summary = services.annotate(
            total_today=Count("tickets", filter=Q(tickets__created_at__date=today)),
            pending_total=Count("tickets", filter=Q(tickets__status__in=pending_statuses)),
            skipped_total=Count("tickets", filter=Q(tickets__status=QueueTicket.Status.SKIPPED)),
            completed_total=Count("tickets", filter=Q(tickets__status=QueueTicket.Status.COMPLETED)),
            counter_total=Count("counters", filter=Q(counters__is_active=True), distinct=True),
        ).order_by("-total_today", "name", "code")
        active_queue_services = [service for service in service_summary if service.pending_total > 0]
        reached_max_services = services.filter(
            is_active=True,
            current_queue_number__gte=F("max_queue_limit"),
        ).order_by("name", "code")
        busiest_service_today = next((service for service in service_summary if service.total_today > 0), None)
        active_counters = counters.select_related("assigned_service").filter(is_active=True).order_by("name")
        queue_history = QueueHistoryLog.objects.all()
        if company:
            queue_history = queue_history.filter(company=company)

        context.update(
            {
                "organization_name": self.request.user.company.name if self.request.user.company_id else "AquiSo Platform",
                "can_manage_organizations": self.request.user.can_manage_companies(),
                "can_manage_queue_setup": self.request.user.role == User.Role.SUPER_ADMIN,
                "today": today,
                "service_count": services.count(),
                "counter_count": counters.count(),
                "waiting_ticket_count": tickets.filter(status=QueueTicket.Status.WAITING).count(),
                "display_screen_count": screens.count(),
                "history_log_count": queue_history.count(),
                "total_queued_today": tickets.filter(created_at__date=today).count(),
                "total_served_today": tickets.filter(called_at__date=today).exclude(status=QueueTicket.Status.WAITING).count(),
                "total_pending": tickets.filter(status__in=pending_statuses).count(),
                "total_skipped": tickets.filter(status=QueueTicket.Status.SKIPPED).count(),
                "total_completed": tickets.filter(status=QueueTicket.Status.COMPLETED).count(),
                "active_services": services.filter(is_active=True).order_by("name")[:5],
                "ticket_generation_services": services.filter(
                    is_active=True,
                    show_in_ticket_generation=True,
                ).order_by("name", "code")[:5],
                "service_summary": service_summary,
                "active_queue_services": active_queue_services,
                "reached_max_services": reached_max_services,
                "busiest_service_today": busiest_service_today,
                "active_counters": active_counters[:8],
                "ticket_status_rows": list(
                    tickets.values("status").annotate(total=Count("id")).order_by("status")
                ),
                "queue_settings": settings_record.first(),
            }
        )
        return context


class QueueSystemSettingListView(QueueingSuperAdminAccessMixin, ListView):
    model = QueueSystemSetting
    template_name = "queueing/setting_list.html"
    context_object_name = "settings_records"

    def get_queryset(self):
        queryset = QueueSystemSetting.objects.select_related("company").order_by("company__name")
        return self._company_queryset(queryset)


class QueueSystemSettingCreateView(QueueingSuperAdminAccessMixin, CreateView):
    model = QueueSystemSetting
    form_class = QueueSystemSettingForm
    template_name = "queueing/setting_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Queue system settings created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue system settings creation failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:setting-list")


class QueueSystemSettingUpdateView(QueueingSuperAdminAccessMixin, UpdateView):
    model = QueueSystemSetting
    form_class = QueueSystemSettingForm
    template_name = "queueing/setting_form.html"

    def get_queryset(self):
        queryset = QueueSystemSetting.objects.select_related("company")
        return self._company_queryset(queryset)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Queue system settings updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue system settings update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:setting-list")


class QueueTicketCreateView(QueueingSetupMixin, FormView):
    form_class = QueueTicketGenerationForm
    template_name = "queueing/ticket_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_id = self.request.GET.get("service")
        selected_service = None
        if service_id:
            queryset = self._company_queryset(QueueService.objects.all())
            selected_service = queryset.filter(pk=service_id).first()
        context.update(
            {
                "selected_service": selected_service,
                "can_edit_selected_service": bool(selected_service and self.request.user.role == User.Role.SUPER_ADMIN),
            }
        )
        return context

    def form_valid(self, form):
        service = form.cleaned_data["service"]
        is_priority = form.cleaned_data["is_priority"]

        with transaction.atomic():
            locked_service = QueueService.objects.select_for_update().get(pk=service.pk)
            if not locked_service.is_active:
                form.add_error("service", "This service is inactive and cannot generate tickets.")
                messages.error(self.request, "This service is inactive and cannot generate tickets.")
                return self.form_invalid(form)
            if not locked_service.show_in_ticket_generation:
                form.add_error("service", "This service is not available for ticket generation.")
                messages.error(self.request, "This service is not available for ticket generation.")
                return self.form_invalid(form)
            if locked_service.current_queue_number >= locked_service.max_queue_limit:
                form.add_error("service", "Maximum queue limit reached for this service")
                messages.error(self.request, "Maximum queue limit reached for this service")
                return self.form_invalid(form)

            locked_service.current_queue_number += 1
            locked_service.save(update_fields=["current_queue_number", "updated_at"])

            queue_number = f"{locked_service.code}{locked_service.current_queue_number:03d}"
            ticket = QueueTicket.objects.create(
                company=locked_service.company,
                queue_number=queue_number,
                service=locked_service,
                is_priority=is_priority,
            )
            _log_queue_action(
                ticket=ticket,
                actor=self.request.user,
                action=QueueHistoryLog.Action.CREATED,
                notes="Queue ticket generated from the setup page.",
            )

        messages.success(self.request, f"Queue ticket {queue_number} created successfully.")
        return redirect("queueing:ticket-success", pk=ticket.pk)

    def form_invalid(self, form):
        if form.non_field_errors():
            messages.error(self.request, form.non_field_errors()[0])
        else:
            messages.error(self.request, "Queue ticket creation failed. Please review the form and try again.")
        return super().form_invalid(form)


class QueueTicketSuccessView(QueueingSetupMixin, DetailView):
    model = QueueTicket
    template_name = "queueing/ticket_success.html"
    context_object_name = "ticket"

    def get_queryset(self):
        queryset = QueueTicket.objects.select_related("company", "service", "assigned_counter")
        return self._company_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "can_edit_service_settings": self.request.user.role == User.Role.SUPER_ADMIN,
            }
        )
        return context


class QueueDisplayScreenView(DetailView):
    model = QueueDisplayScreen
    template_name = "queueing/display_screen_view.html"
    context_object_name = "screen"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return QueueDisplayScreen.objects.filter(is_active=True).prefetch_related("services")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        screen = self.object
        services = screen.services.filter(is_active=True).order_by("name", "code")
        tickets = QueueTicket.objects.select_related("service", "assigned_counter").filter(
            company=screen.company,
            service__in=services,
        )
        current_ticket = tickets.filter(status__in=[QueueTicket.Status.SERVING, QueueTicket.Status.CALLED]).order_by(
            "-called_at", "-created_at", "-id"
        ).first()
        recent_called_tickets = tickets.filter(
            Q(status=QueueTicket.Status.CALLED)
            | Q(status=QueueTicket.Status.SERVING)
            | Q(status=QueueTicket.Status.COMPLETED)
        ).order_by("-called_at", "-completed_at", "-created_at", "-id")[:10]

        context.update(
            {
                "current_ticket": current_ticket,
                "recent_called_tickets": recent_called_tickets,
                "screen_services": services,
            }
        )
        return context


class QueueMonitorListView(QueueingSetupMixin, ListView):
    model = QueueDisplayScreen
    template_name = "queueing/monitor_list.html"
    context_object_name = "screens"

    def get_queryset(self):
        queryset = QueueDisplayScreen.objects.select_related("company").prefetch_related("services").filter(is_active=True)
        return self._company_queryset(queryset.order_by("name"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        screen_rows = []
        for screen in context["screens"]:
            services = screen.services.filter(is_active=True).order_by("name", "code")
            current_ticket = QueueTicket.objects.select_related("service", "assigned_counter").filter(
                company=screen.company,
                service__in=services,
                status__in=[QueueTicket.Status.SERVING, QueueTicket.Status.CALLED],
            ).order_by("-called_at", "-created_at", "-id").first()
            screen_rows.append(
                {
                    "screen": screen,
                    "services": services,
                    "current_ticket": current_ticket,
                }
            )
        context["screen_rows"] = screen_rows
        return context


class QueueMonitorView(DetailView):
    model = QueueDisplayScreen
    template_name = "queueing/monitor_view.html"
    context_object_name = "screen"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return QueueDisplayScreen.objects.filter(is_active=True).prefetch_related("services")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        screen = self.object
        services = screen.services.filter(is_active=True).order_by("name", "code")
        tickets = QueueTicket.objects.select_related("service", "assigned_counter").filter(
            company=screen.company,
            service__in=services,
        )
        current_ticket = tickets.filter(
            status__in=[QueueTicket.Status.SERVING, QueueTicket.Status.CALLED],
        ).order_by("-called_at", "-created_at", "-id").first()
        next_ticket = tickets.filter(
            status=QueueTicket.Status.WAITING,
        ).order_by("created_at", "id").first()
        total_served_today = tickets.filter(
            status=QueueTicket.Status.COMPLETED,
            completed_at__date=timezone.localdate(),
        ).count()
        waiting_count = tickets.filter(status=QueueTicket.Status.WAITING).count()
        current_started_at = current_ticket.called_at if current_ticket and current_ticket.called_at else None
        context.update(
            {
                "screen_services": services,
                "current_ticket": current_ticket,
                "next_ticket": next_ticket,
                "total_served_today": total_served_today,
                "waiting_count": waiting_count,
                "current_started_at": current_started_at,
                "current_timestamp": timezone.localtime(),
            }
        )
        return context


class QueueOperatorPanelView(QueueingSetupMixin, TemplateView):
    template_name = "queueing/operator_panel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tickets = self._company_queryset(
            QueueTicket.objects.select_related("service", "assigned_counter", "company").order_by("created_at", "id")
        )
        services = self._company_queryset(QueueService.objects.order_by("name", "code"))
        context.update(
            {
                "call_next_form": kwargs.get("call_next_form") or QueueCallNextForm(company=self.request.user.company),
                "waiting_tickets": tickets.filter(status=QueueTicket.Status.WAITING),
                "called_tickets": tickets.filter(status=QueueTicket.Status.CALLED),
                "serving_tickets": tickets.filter(status=QueueTicket.Status.SERVING),
                "skipped_tickets": tickets.filter(status=QueueTicket.Status.SKIPPED),
                "recent_completed_tickets": tickets.filter(status=QueueTicket.Status.COMPLETED)[:10],
                "services": services,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("queue_action", "").strip()
        if action == "call_next":
            return self._call_next(request)
        if action in {"call_specific", "mark_serving", "mark_done", "skip", "recall"}:
            return self._update_ticket_action(request, action)
        messages.error(request, "Unknown queue action.")
        return redirect("queueing:operator-panel")

    def _call_next(self, request):
        form = QueueCallNextForm(request.POST, company=request.user.company)
        if not form.is_valid():
            messages.error(request, "Call next failed. Please review the form and try again.")
            return self.render_to_response(self.get_context_data(call_next_form=form))

        service = form.cleaned_data["service"]
        counter = form.cleaned_data["counter"]
        ticket = self._company_queryset(
            QueueTicket.objects.filter(service=service, status=QueueTicket.Status.WAITING).order_by("created_at", "id")
        ).first()
        if not ticket:
            messages.error(request, "No waiting tickets are available for that service.")
            return redirect("queueing:operator-panel")

        ticket.status = QueueTicket.Status.CALLED
        ticket.assigned_counter = counter
        ticket.called_at = timezone.now()
        ticket.save(update_fields=["status", "assigned_counter", "called_at"])
        _log_queue_action(
            ticket=ticket,
            actor=request.user,
            action=QueueHistoryLog.Action.CALLED,
            notes="Called from operator panel using call next.",
            counter=counter,
            service=service,
        )
        messages.success(request, f"{ticket.queue_number} called successfully.")
        return redirect("queueing:operator-panel")

    def _update_ticket_action(self, request, action):
        ticket = get_object_or_404(
            self._company_queryset(QueueTicket.objects.select_related("service", "assigned_counter")),
            pk=request.POST.get("ticket_id"),
        )
        counter = None
        counter_id = request.POST.get("counter", "").strip()
        if counter_id:
            counter = get_object_or_404(self._company_queryset(QueueCounter.objects.all()), pk=counter_id)

        now = timezone.now()
        if action == "call_specific":
            ticket.status = QueueTicket.Status.CALLED
            if counter is not None:
                ticket.assigned_counter = counter
            ticket.called_at = now
            update_fields = ["status", "called_at"]
            if counter is not None:
                update_fields.append("assigned_counter")
            ticket.save(update_fields=update_fields)
            _log_queue_action(
                ticket=ticket,
                actor=request.user,
                action=QueueHistoryLog.Action.CALLED,
                notes="Specific queue called from operator panel.",
                counter=counter,
            )
            messages.success(request, f"{ticket.queue_number} called successfully.")
        elif action == "mark_serving":
            ticket.status = QueueTicket.Status.SERVING
            if counter is not None:
                ticket.assigned_counter = counter
                ticket.save(update_fields=["status", "assigned_counter"])
            else:
                ticket.save(update_fields=["status"])
            _log_queue_action(
                ticket=ticket,
                actor=request.user,
                action=QueueHistoryLog.Action.SERVING,
                notes="Queue marked as serving.",
                counter=counter,
            )
            messages.success(request, f"{ticket.queue_number} marked as serving.")
        elif action == "mark_done":
            ticket.status = QueueTicket.Status.COMPLETED
            ticket.completed_at = now
            ticket.save(update_fields=["status", "completed_at"])
            _log_queue_action(
                ticket=ticket,
                actor=request.user,
                action=QueueHistoryLog.Action.COMPLETED,
                notes="Queue marked as completed.",
            )
            messages.success(request, f"{ticket.queue_number} marked as done.")
        elif action == "skip":
            ticket.status = QueueTicket.Status.SKIPPED
            ticket.save(update_fields=["status"])
            _log_queue_action(
                ticket=ticket,
                actor=request.user,
                action=QueueHistoryLog.Action.SKIPPED,
                notes="Queue skipped from operator panel.",
            )
            messages.success(request, f"{ticket.queue_number} skipped.")
        elif action == "recall":
            ticket.status = QueueTicket.Status.CALLED
            ticket.called_at = now
            update_fields = ["status", "called_at"]
            if counter is not None:
                ticket.assigned_counter = counter
                update_fields.append("assigned_counter")
            ticket.save(update_fields=update_fields)
            _log_queue_action(
                ticket=ticket,
                actor=request.user,
                action=QueueHistoryLog.Action.RECALL,
                notes="Queue recalled from operator panel.",
                counter=counter,
            )
            messages.success(request, f"{ticket.queue_number} recalled.")
        return redirect("queueing:operator-panel")


class QueueServiceListView(QueueingSuperAdminAccessMixin, ListView):
    model = QueueService
    template_name = "queueing/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        queryset = QueueService.objects.select_related("company").order_by("name", "code")
        return self._company_queryset(queryset)


class QueueServiceCreateView(QueueingSuperAdminAccessMixin, CreateView):
    model = QueueService
    form_class = QueueServiceForm
    template_name = "queueing/service_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Queue service created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue service creation failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:service-list")


class QueueServiceUpdateView(QueueingSuperAdminAccessMixin, UpdateView):
    model = QueueService
    form_class = QueueServiceForm
    template_name = "queueing/service_form.html"

    def get_queryset(self):
        queryset = QueueService.objects.select_related("company")
        return self._company_queryset(queryset)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        original = QueueService.objects.get(pk=self.get_object().pk)
        field_labels = [
            ("name", "Name"),
            ("code", "Code"),
            ("max_queue_limit", "Max Queue"),
            ("current_queue_number", "Current Queue"),
            ("is_active", "Active"),
            ("show_in_ticket_generation", "Ticket Generation"),
        ]
        response = super().form_valid(form)
        _log_queue_action(
            actor=self.request.user,
            action=QueueHistoryLog.Action.SERVICE_UPDATED,
            company=self.object.company,
            service=self.object,
            notes=_summarize_changes(field_labels, original, self.object),
        )
        messages.success(self.request, "Queue service updated successfully.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Queue service update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:service-list")


class QueueServiceDeleteView(QueueingSuperAdminAccessMixin, View):
    def post(self, request, *args, **kwargs):
        service = get_object_or_404(
            self._company_queryset(QueueService.objects.all()),
            pk=kwargs["pk"],
        )
        if service.tickets.exists() or service.counters.exists() or service.display_screens.exists():
            messages.error(
                request,
                "Queue service cannot be deleted while it is linked to tickets, counters, or display screens.",
            )
            return redirect("queueing:service-update", pk=service.pk)

        service_name = service.name
        service.delete()
        messages.success(request, f"Queue service {service_name} deleted successfully.")
        return redirect("queueing:service-list")


class QueueTicketUpdateView(QueueingSetupMixin, UpdateView):
    model = QueueTicket
    form_class = QueueTicketUpdateForm
    template_name = "queueing/ticket_update_form.html"

    def get_queryset(self):
        queryset = QueueTicket.objects.select_related("company", "service", "assigned_counter")
        return self._company_queryset(queryset)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        original = QueueTicket.objects.get(pk=self.get_object().pk)
        old_service = original.service
        old_counter = original.assigned_counter
        old_status = original.status
        old_priority = original.is_priority
        if form.cleaned_data["status"] == QueueTicket.Status.CALLED and not form.instance.called_at:
            form.instance.called_at = timezone.now()
        if form.cleaned_data["status"] == QueueTicket.Status.COMPLETED and not form.instance.completed_at:
            form.instance.completed_at = timezone.now()
        response = super().form_valid(form)

        if old_service != self.object.service or old_counter != self.object.assigned_counter:
            _log_queue_action(
                ticket=self.object,
                actor=self.request.user,
                action=QueueHistoryLog.Action.REASSIGNED,
                notes="Ticket service or counter adjusted manually.",
            )
        if old_status != self.object.status:
            action_map = {
                QueueTicket.Status.CALLED: QueueHistoryLog.Action.CALLED,
                QueueTicket.Status.SERVING: QueueHistoryLog.Action.SERVING,
                QueueTicket.Status.COMPLETED: QueueHistoryLog.Action.COMPLETED,
                QueueTicket.Status.SKIPPED: QueueHistoryLog.Action.SKIPPED,
                QueueTicket.Status.CANCELLED: QueueHistoryLog.Action.CANCELLED,
            }
            history_action = action_map.get(self.object.status)
            if history_action:
                _log_queue_action(
                    ticket=self.object,
                    actor=self.request.user,
                    action=history_action,
                    notes="Ticket status adjusted manually.",
                )
        if (
            old_service != self.object.service
            or old_counter != self.object.assigned_counter
            or old_status != self.object.status
            or old_priority != self.object.is_priority
        ):
            _log_queue_action(
                ticket=self.object,
                actor=self.request.user,
                action=QueueHistoryLog.Action.MANUAL_EDITED,
                notes="Ticket edited manually from the queue operator panel.",
            )

        messages.success(self.request, "Queue ticket updated successfully.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Queue ticket update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:operator-panel")


class QueueCounterListView(QueueingSuperAdminAccessMixin, ListView):
    model = QueueCounter
    template_name = "queueing/counter_list.html"
    context_object_name = "counters"

    def get_queryset(self):
        queryset = QueueCounter.objects.select_related("company", "assigned_service").order_by("name")
        return self._company_queryset(queryset)


class QueueCounterCreateView(QueueingSuperAdminAccessMixin, CreateView):
    model = QueueCounter
    form_class = QueueCounterForm
    template_name = "queueing/counter_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Queue counter created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue counter creation failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:counter-list")


class QueueCounterUpdateView(QueueingSuperAdminAccessMixin, UpdateView):
    model = QueueCounter
    form_class = QueueCounterForm
    template_name = "queueing/counter_form.html"

    def get_queryset(self):
        queryset = QueueCounter.objects.select_related("company", "assigned_service")
        return self._company_queryset(queryset)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        original = QueueCounter.objects.get(pk=self.get_object().pk)
        field_labels = [
            ("name", "Name"),
            ("assigned_service", "Assigned Service"),
            ("is_active", "Active"),
        ]
        response = super().form_valid(form)
        _log_queue_action(
            actor=self.request.user,
            action=QueueHistoryLog.Action.COUNTER_UPDATED,
            company=self.object.company,
            service=self.object.assigned_service,
            counter=self.object,
            notes=_summarize_changes(field_labels, original, self.object),
        )
        messages.success(self.request, "Queue counter updated successfully.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Queue counter update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:counter-list")


class QueueDisplayScreenListView(QueueingSuperAdminAccessMixin, ListView):
    model = QueueDisplayScreen
    template_name = "queueing/display_screen_list.html"
    context_object_name = "screens"

    def get_queryset(self):
        queryset = QueueDisplayScreen.objects.select_related("company").prefetch_related("services").order_by("name")
        return self._company_queryset(queryset)


class QueueDisplayScreenCreateView(QueueingSuperAdminAccessMixin, CreateView):
    model = QueueDisplayScreen
    form_class = QueueDisplayScreenForm
    template_name = "queueing/display_screen_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Display screen created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Display screen creation failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:display-screen-list")


class QueueDisplayScreenUpdateView(QueueingSuperAdminAccessMixin, UpdateView):
    model = QueueDisplayScreen
    form_class = QueueDisplayScreenForm
    template_name = "queueing/display_screen_form.html"

    def get_queryset(self):
        queryset = QueueDisplayScreen.objects.select_related("company").prefetch_related("services")
        return self._company_queryset(queryset)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(self._form_kwargs())
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Display screen updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Display screen update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:display-screen-list")


class QueueHistoryListView(QueueingSuperAdminAccessMixin, ListView):
    model = QueueHistoryLog
    template_name = "queueing/history_list.html"
    context_object_name = "history_logs"
    paginate_by = 50

    def get_queryset(self):
        queryset = self._company_queryset(
            QueueHistoryLog.objects.select_related(
                "company",
                "ticket",
                "service",
                "counter",
                "actor",
            ).order_by("-created_at", "-id")
        )
        date_value = self.request.GET.get("date", "").strip()
        service_id = self.request.GET.get("service", "").strip()
        status_value = self.request.GET.get("status", "").strip()
        counter_id = self.request.GET.get("counter", "").strip()

        if date_value:
            queryset = queryset.filter(created_at__date=date_value)
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        if status_value:
            queryset = queryset.filter(status_snapshot=status_value)
        if counter_id:
            queryset = queryset.filter(counter_id=counter_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_queryset = self._company_queryset(QueueService.objects.order_by("name", "code"))
        counter_queryset = self._company_queryset(QueueCounter.objects.order_by("name"))
        context.update(
            {
                "services": service_queryset,
                "counters": counter_queryset,
                "status_choices": QueueTicket.Status.choices,
                "selected_date": self.request.GET.get("date", "").strip(),
                "selected_service": self.request.GET.get("service", "").strip(),
                "selected_status": self.request.GET.get("status", "").strip(),
                "selected_counter": self.request.GET.get("counter", "").strip(),
            }
        )
        return context
