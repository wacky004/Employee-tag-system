from django.urls import path

from .views import SuperAdminSettingsView

app_name = "core"

urlpatterns = [
    path("settings/", SuperAdminSettingsView.as_view(), name="settings"),
]
