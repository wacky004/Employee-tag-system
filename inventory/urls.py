from django.urls import path

from .views import (
    EmployeeAssignSupervisorView,
    EmployeeCreateView,
    EmployeeListView,
    EquipmentAssignmentCreateView,
    EquipmentCreateView,
    EquipmentDetailView,
    EquipmentHistoryView,
    InventoryDashboardView,
    InventorySummaryView,
    SupervisorCreateView,
    SupervisorListView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("summary/", InventorySummaryView.as_view(), name="summary"),
    path("supervisors/", SupervisorListView.as_view(), name="supervisor-list"),
    path("supervisors/create/", SupervisorCreateView.as_view(), name="supervisor-create"),
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/assign-supervisor/", EmployeeAssignSupervisorView.as_view(), name="employee-assign-supervisor"),
    path("equipment/assign/", EquipmentAssignmentCreateView.as_view(), name="equipment-assign"),
    path("equipment/create/", EquipmentCreateView.as_view(), name="equipment-create"),
    path("equipment/<int:pk>/history/", EquipmentHistoryView.as_view(), name="equipment-history"),
    path("equipment/<int:pk>/", EquipmentDetailView.as_view(), name="equipment-detail"),
]
