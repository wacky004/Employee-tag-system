from django.urls import path

from .views import (
    QueueCounterCreateView,
    QueueCounterListView,
    QueueCounterUpdateView,
    QueueDisplayScreenCreateView,
    QueueDisplayScreenListView,
    QueueDisplayScreenUpdateView,
    QueueServiceCreateView,
    QueueServiceListView,
    QueueServiceUpdateView,
    QueueingDashboardView,
)

app_name = "queueing"

urlpatterns = [
    path("", QueueingDashboardView.as_view(), name="dashboard"),
    path("services/", QueueServiceListView.as_view(), name="service-list"),
    path("services/create/", QueueServiceCreateView.as_view(), name="service-create"),
    path("services/<int:pk>/edit/", QueueServiceUpdateView.as_view(), name="service-update"),
    path("counters/", QueueCounterListView.as_view(), name="counter-list"),
    path("counters/create/", QueueCounterCreateView.as_view(), name="counter-create"),
    path("counters/<int:pk>/edit/", QueueCounterUpdateView.as_view(), name="counter-update"),
    path("display-screens/", QueueDisplayScreenListView.as_view(), name="display-screen-list"),
    path("display-screens/create/", QueueDisplayScreenCreateView.as_view(), name="display-screen-create"),
    path("display-screens/<int:pk>/edit/", QueueDisplayScreenUpdateView.as_view(), name="display-screen-update"),
]
