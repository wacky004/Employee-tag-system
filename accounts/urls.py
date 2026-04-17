from django.urls import path

from .views import (
    CompanyManagementView,
    DashboardRedirectView,
    EmployeeDashboardView,
    ManagerDashboardView,
    ModuleAccessManagementView,
    RoleBasedLoginView,
    SuperAdminDashboardView,
)

app_name = "accounts"

urlpatterns = [
    path("", DashboardRedirectView.as_view(), name="home"),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    path("dashboard/", DashboardRedirectView.as_view(), name="dashboard"),
    path("dashboard/employee/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
    path("dashboard/manager/", ManagerDashboardView.as_view(), name="manager-dashboard"),
    path("dashboard/super-admin/", SuperAdminDashboardView.as_view(), name="super-admin-dashboard"),
    path("dashboard/super-admin/organizations/", CompanyManagementView.as_view(), name="company-management"),
    path("dashboard/super-admin/module-access/", ModuleAccessManagementView.as_view(), name="module-access"),
]
