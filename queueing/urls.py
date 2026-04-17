from django.urls import path

from .views import QueueingDashboardView

app_name = "queueing"

urlpatterns = [
    path("", QueueingDashboardView.as_view(), name="dashboard"),
]

