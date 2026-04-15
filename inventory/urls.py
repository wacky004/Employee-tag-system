from django.urls import path

from .views import EquipmentCreateView, InventoryDashboardView

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("equipment/create/", EquipmentCreateView.as_view(), name="equipment-create"),
]
