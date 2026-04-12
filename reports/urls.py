from django.urls import path

from .views import ReportCenterView

app_name = "reports"

urlpatterns = [
    path("", ReportCenterView.as_view(), name="center"),
]
