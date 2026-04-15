from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from .models import TagLog, TagType

User = get_user_model()


def _dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class TaggingAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = (User.Role.SUPER_ADMIN,)

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(_dashboard_url(self.request.user))
        return super().handle_no_permission()


class TaggingDashboardView(TaggingAccessMixin, TemplateView):
    template_name = "tagging/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        work_date = timezone.localdate()
        today_logs = TagLog.objects.select_related("employee", "tag_type").filter(work_date=work_date)
        summary_rows = (
            today_logs.values("tag_type__name")
            .annotate(total=Count("id"))
            .order_by("tag_type__name")
        )

        context.update(
            {
                "work_date": work_date,
                "total_logs_today": today_logs.count(),
                "employees_tagged_today": today_logs.values("employee_id").distinct().count(),
                "active_tag_types": TagType.objects.filter(is_active=True).count(),
                "recent_logs": list(today_logs.order_by("-timestamp", "-id")[:10]),
                "summary_rows": list(summary_rows),
            }
        )
        return context
