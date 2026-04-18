from io import BytesIO

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.views.generic import TemplateView

from accounts.views import RoleRequiredMixin

from .services import build_report_dataset, export_dataset_to_csv, get_filter_options, normalize_filters

User = get_user_model()


class ReportCenterView(RoleRequiredMixin, TemplateView):
    template_name = "reports/report_center.html"
    allowed_roles = (User.Role.ADMIN, User.Role.SUPER_ADMIN)

    def test_func(self):
        return super().test_func() and self.request.user.has_tagging_module_access()

    def get(self, request, *args, **kwargs):
        filters = normalize_filters(request.GET)
        company = request.user.company if request.user.company_id else None
        dataset = build_report_dataset(filters, company=company)
        export_format = request.GET.get("export", "html")

        if export_format == "csv":
            return self._csv_response(dataset, filters["report_type"])
        if export_format == "xlsx":
            return self._xlsx_response(dataset, filters["report_type"])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = normalize_filters(self.request.GET)
        company = self.request.user.company if self.request.user.company_id else None
        dataset = build_report_dataset(filters, company=company)
        context.update(get_filter_options(company=company))
        context.update(
            {
                "dataset": dataset,
                "filters": filters,
                "print_mode": self.request.GET.get("print") == "1",
            }
        )
        return context

    def _csv_response(self, dataset, report_type):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{report_type}-report.csv"'
        export_dataset_to_csv(dataset, response)
        return response

    def _xlsx_response(self, dataset, report_type):
        try:
            from openpyxl import Workbook
        except ModuleNotFoundError:
            return HttpResponse(
                "Excel export requires openpyxl. Install project dependencies with pip install -r requirements.txt.",
                status=503,
                content_type="text/plain",
            )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Report"
        sheet.append(dataset["columns"])
        for row in dataset["rows"]:
            sheet.append([row.get(key, "") for key in dataset["column_keys"]])

        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)

        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{report_type}-report.xlsx"'
        return response
