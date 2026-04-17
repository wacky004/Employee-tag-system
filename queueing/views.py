from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from .models import QueueCounter, QueueDisplayScreen, QueueService, QueueSystemSetting, QueueTicket

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
                "ticket_status_rows": list(
                    tickets.values("status").annotate(total=Count("id")).order_by("status")
                ),
                "queue_settings": settings_record.first(),
            }
        )
        return context
