from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from attendance.services import refresh_attendance_session
from tagging.models import TagLog

User = get_user_model()


class Command(BaseCommand):
    help = "Refresh attendance session summaries from raw tag logs."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="work_date", help="Work date in YYYY-MM-DD format.")
        parser.add_argument("--employee", dest="employee_id", type=int, help="Specific employee user ID.")

    def handle(self, *args, **options):
        work_date = self._parse_date(options.get("work_date"))
        employee_id = options.get("employee_id")

        logs = TagLog.objects.select_related("employee")
        if work_date:
            logs = logs.filter(work_date=work_date)
        if employee_id:
            logs = logs.filter(employee_id=employee_id)

        targets = logs.values_list("employee_id", "work_date").distinct()
        if not targets:
            self.stdout.write(self.style.WARNING("No tag logs found for the given filters."))
            return

        refreshed = 0
        for target_employee_id, target_work_date in targets:
            employee = User.objects.get(pk=target_employee_id)
            refresh_attendance_session(employee, target_work_date)
            refreshed += 1

        self.stdout.write(self.style.SUCCESS(f"Refreshed {refreshed} attendance session(s)."))

    def _parse_date(self, raw_value):
        if not raw_value:
            return None
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise CommandError("Date must be in YYYY-MM-DD format.") from exc
