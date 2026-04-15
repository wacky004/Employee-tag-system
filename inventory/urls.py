from django.urls import path

from .views import (
    EmployeeAssignSupervisorView,
    EmployeeCreateView,
    EmployeeDetailView,
    EmployeeListView,
    EmployeeSearchView,
    EquipmentAssignmentCreateView,
    EquipmentCreateView,
    EquipmentDetailView,
    EquipmentHistoryView,
    EquipmentUpdateView,
    InventoryDashboardView,
    InventorySummaryView,
    SupervisorCreateView,
    SupervisorListView,
    SupervisorUpdateView,
    EmployeeUpdateView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("summary/", InventorySummaryView.as_view(), name="summary"),
    path("supervisors/", SupervisorListView.as_view(), name="supervisor-list"),
    path("supervisors/create/", SupervisorCreateView.as_view(), name="supervisor-create"),
    path("supervisors/<int:pk>/edit/", SupervisorUpdateView.as_view(), name="supervisor-update"),
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/search/", EmployeeSearchView.as_view(), name="employee-search"),
    path("employees/<int:pk>/edit/", EmployeeUpdateView.as_view(), name="employee-update"),
    path("employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("employees/assign-supervisor/", EmployeeAssignSupervisorView.as_view(), name="employee-assign-supervisor"),
    path("equipment/assign/", EquipmentAssignmentCreateView.as_view(), name="equipment-assign"),
    path("equipment/create/", EquipmentCreateView.as_view(), name="equipment-create"),
    path("equipment/<int:pk>/edit/", EquipmentUpdateView.as_view(), name="equipment-update"),
    path("equipment/<int:pk>/history/", EquipmentHistoryView.as_view(), name="equipment-history"),
    path("equipment/<int:pk>/", EquipmentDetailView.as_view(), name="equipment-detail"),
]
