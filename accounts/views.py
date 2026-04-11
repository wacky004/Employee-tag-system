from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, View

User = get_user_model()


def get_dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return get_dashboard_url(self.request.user)


class DashboardRedirectView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(get_dashboard_url(request.user))


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(get_dashboard_url(self.request.user))
        return super().handle_no_permission()


class EmployeeDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/employee_dashboard.html"
    allowed_roles = (User.Role.EMPLOYEE,)


class ManagerDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/manager_dashboard.html"
    allowed_roles = (User.Role.ADMIN,)


class SuperAdminDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/super_admin_dashboard.html"
    allowed_roles = (User.Role.SUPER_ADMIN,)
