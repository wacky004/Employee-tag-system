"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.admin import tenant_admin_site

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("core.urls")),
    path("", include("attendance.urls")),
    path("inventory/", include("inventory.urls")),
    path("queueing/", include("queueing.urls")),
    path("tagging/", include("tagging.urls")),
    path("reports/", include("reports.urls")),
    path("admin/", admin.site.urls),
    path("tenant-admin/", tenant_admin_site.urls),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
