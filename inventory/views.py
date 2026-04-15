from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

User = get_user_model()


def _dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class InventoryAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(_dashboard_url(self.request.user))
        return super().handle_no_permission()


class InventoryDashboardView(InventoryAccessMixin, TemplateView):
    template_name = "inventory/dashboard.html"
