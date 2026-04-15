from django.urls import path

from .views import (
    EmployeeAssignSupervisorView,
    EmployeeCreateView,
    EmployeeListView,
    EquipmentCreateView,
    InventoryDashboardView,
    SupervisorCreateView,
    SupervisorListView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("supervisors/", SupervisorListView.as_view(), name="supervisor-list"),
    path("supervisors/create/", SupervisorCreateView.as_view(), name="supervisor-create"),
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/assign-supervisor/", EmployeeAssignSupervisorView.as_view(), name="employee-assign-supervisor"),
    path("equipment/create/", EquipmentCreateView.as_view(), name="equipment-create"),
]
