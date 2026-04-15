from django.urls import path

from .views import TaggingDashboardView

app_name = "tagging"

urlpatterns = [
    path("", TaggingDashboardView.as_view(), name="dashboard"),
]
