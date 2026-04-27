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
    def test_func(self):
        return self.request.user.has_tagging_module_access()

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
        if self.request.user.company_id:
            today_logs = today_logs.filter(employee__company=self.request.user.company)
        summary_rows = (
            today_logs.values("tag_type__name")
            .annotate(total=Count("id"))
            .order_by("tag_type__name")
        )
        effective_tag_types = TagType.effective_for_company(self.request.user.company if self.request.user.company_id else None)

        context.update(
            {
                "work_date": work_date,
                "total_logs_today": today_logs.count(),
                "employees_tagged_today": today_logs.values("employee_id").distinct().count(),
                "active_tag_types": len(effective_tag_types),
                "recent_logs": list(today_logs.order_by("-timestamp", "-id")[:10]),
                "summary_rows": list(summary_rows),
            }
        )
        return context
