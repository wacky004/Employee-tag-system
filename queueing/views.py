from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from .forms import QueueCounterForm, QueueDisplayScreenForm, QueueServiceForm, QueueTicketGenerationForm
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

        context.update(
            {
                "organization_name": self.request.user.company.name if self.request.user.company_id else "AquiSo Platform",
                "can_manage_organizations": self.request.user.can_manage_companies(),
                "service_count": services.count(),
                "counter_count": counters.count(),
                "waiting_ticket_count": tickets.filter(status=QueueTicket.Status.WAITING).count(),
                "display_screen_count": screens.count(),
                "active_services": services.filter(is_active=True).order_by("name")[:5],
                "ticket_generation_services": services.filter(
                    is_active=True,
                    show_in_ticket_generation=True,
                ).order_by("name", "code")[:5],
                "ticket_status_rows": list(
                    tickets.values("status").annotate(total=Count("id")).order_by("status")
                ),
                "queue_settings": settings_record.first(),
            }
        )
        return context


class QueueTicketCreateView(QueueingSetupMixin, FormView):
    form_class = QueueTicketGenerationForm
    template_name = "queueing/ticket_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        service = form.cleaned_data["service"]
        is_priority = form.cleaned_data["is_priority"]

        with transaction.atomic():
            locked_service = QueueService.objects.select_for_update().get(pk=service.pk)
            if locked_service.current_queue_number >= locked_service.max_queue_limit:
                form.add_error("service", "Maximum queue limit reached for this service")
                messages.error(self.request, "Maximum queue limit reached for this service")
                return self.form_invalid(form)

            locked_service.current_queue_number += 1
            locked_service.save(update_fields=["current_queue_number", "updated_at"])

            queue_number = f"{locked_service.code}-{locked_service.current_queue_number:03d}"
            ticket = QueueTicket.objects.create(
                company=locked_service.company,
                queue_number=queue_number,
                service=locked_service,
                is_priority=is_priority,
            )
            QueueHistoryLog.objects.create(
                company=locked_service.company,
                ticket=ticket,
                service=locked_service,
                actor=self.request.user,
                action=QueueHistoryLog.Action.CREATED,
                notes="Queue ticket generated from the setup page.",
            )

        messages.success(self.request, f"Queue ticket {queue_number} created successfully.")
        return redirect("queueing:ticket-create")

    def form_invalid(self, form):
        if form.non_field_errors():
            messages.error(self.request, form.non_field_errors()[0])
        else:
            messages.error(self.request, "Queue ticket creation failed. Please review the form and try again.")
        return super().form_invalid(form)


class QueueServiceListView(QueueingSetupMixin, ListView):
    model = QueueService
    template_name = "queueing/service_list.html"
    context_object_name = "services"

    def get_queryset(self):
        queryset = QueueService.objects.select_related("company").order_by("name", "code")
        return self._company_queryset(queryset)


class QueueServiceCreateView(QueueingSetupMixin, CreateView):
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


class QueueServiceUpdateView(QueueingSetupMixin, UpdateView):
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
        messages.success(self.request, "Queue service updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue service update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:service-list")


class QueueCounterListView(QueueingSetupMixin, ListView):
    model = QueueCounter
    template_name = "queueing/counter_list.html"
    context_object_name = "counters"

    def get_queryset(self):
        queryset = QueueCounter.objects.select_related("company", "assigned_service").order_by("name")
        return self._company_queryset(queryset)


class QueueCounterCreateView(QueueingSetupMixin, CreateView):
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


class QueueCounterUpdateView(QueueingSetupMixin, UpdateView):
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
        messages.success(self.request, "Queue counter updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Queue counter update failed. Please review the form and try again.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("queueing:counter-list")


class QueueDisplayScreenListView(QueueingSetupMixin, ListView):
    model = QueueDisplayScreen
    template_name = "queueing/display_screen_list.html"
    context_object_name = "screens"

    def get_queryset(self):
        queryset = QueueDisplayScreen.objects.select_related("company").prefetch_related("services").order_by("name")
        return self._company_queryset(queryset)


class QueueDisplayScreenCreateView(QueueingSetupMixin, CreateView):
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


class QueueDisplayScreenUpdateView(QueueingSetupMixin, UpdateView):
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
