import csv
from datetime import date, timedelta

from django.db.models import Q

from attendance.models import AttendanceSession, OverbreakRecord
from core.models import SystemSetting
from employees.models import Department, EmployeeProfile, Team

DEFAULT_REQUIRED_WORK_MINUTES = 480

REPORT_CHOICES = {
    "daily": "Daily Attendance Report",
    "weekly": "Weekly Summary",
    "monthly": "Monthly Summary",
    "overbreak": "Overbreak Report",
    "missed": "Missed Logs Report",
    "late-undertime": "Late / Undertime Report",
}


def build_report_dataset(filters, company=None):
    report_type = filters["report_type"]
    if report_type == "daily":
        return _daily_report(filters, company=company)
    if report_type == "weekly":
        return _range_summary_report(filters, "Weekly Summary", company=company)
    if report_type == "monthly":
        return _range_summary_report(filters, "Monthly Summary", company=company)
    if report_type == "overbreak":
        return _overbreak_report(filters, company=company)
    if report_type == "missed":
        return _missed_logs_report(filters, company=company)
    return _late_undertime_report(filters, company=company)


def get_filter_options(company=None):
    teams = Team.objects.select_related("department").order_by("name")
    departments = Department.objects.order_by("name")
    employees = EmployeeProfile.objects.select_related("user").order_by(
        "user__first_name", "user__last_name", "employee_code"
    )
    if company is not None:
        teams = teams.filter(members__user__company=company).distinct()
        departments = departments.filter(
            Q(employees__user__company=company) | Q(teams__members__user__company=company)
        ).distinct()
        employees = employees.filter(user__company=company)
    return {
        "teams": teams,
        "departments": departments,
        "employees": employees,
        "report_choices": REPORT_CHOICES,
    }


def normalize_filters(query_params):
    report_type = query_params.get("report", "daily")
    if report_type not in REPORT_CHOICES:
        report_type = "daily"

    today = date.today()
    selected_date = _parse_date(query_params.get("date")) or today

    if report_type == "weekly":
        start_date = _parse_date(query_params.get("start_date")) or (selected_date - timedelta(days=selected_date.weekday()))
        end_date = _parse_date(query_params.get("end_date")) or (start_date + timedelta(days=6))
    elif report_type == "monthly":
        start_date = _parse_date(query_params.get("start_date")) or selected_date.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = _parse_date(query_params.get("end_date")) or (next_month - timedelta(days=1))
    else:
        start_date = _parse_date(query_params.get("start_date")) or selected_date
        end_date = _parse_date(query_params.get("end_date")) or selected_date

    return {
        "report_type": report_type,
        "date": selected_date,
        "start_date": start_date,
        "end_date": end_date,
        "team": query_params.get("team", "").strip(),
        "department": query_params.get("department", "").strip(),
        "employee": query_params.get("employee", "").strip(),
        "work_mode": query_params.get("work_mode", "").strip(),
    }


def export_dataset_to_csv(dataset, response):
    writer = csv.writer(response)
    writer.writerow(dataset["columns"])
    for row in dataset["rows"]:
        writer.writerow([row.get(key, "") for key in dataset["column_keys"]])


def _base_sessions(filters, company=None):
    sessions = AttendanceSession.objects.select_related(
        "employee",
        "employee__employee_profile",
        "employee__employee_profile__team",
        "employee__employee_profile__department",
        "employee__employee_profile__team__department",
    ).filter(work_date__range=(filters["start_date"], filters["end_date"]))
    if company is not None:
        sessions = sessions.filter(employee__company=company)

    team = filters["team"]
    department = filters["department"]
    employee = filters["employee"]
    work_mode = filters["work_mode"]

    if team:
        sessions = sessions.filter(employee__employee_profile__team_id=team)
    if department:
        sessions = sessions.filter(
            Q(employee__employee_profile__department_id=department)
            | Q(employee__employee_profile__team__department_id=department)
        )
    if employee:
        sessions = sessions.filter(employee_id=employee)
    if work_mode:
        sessions = sessions.filter(work_mode=work_mode)
    return sessions.distinct()


def _daily_report(filters, company=None):
    sessions = _base_sessions(filters, company=company).filter(work_date=filters["date"]).order_by(
        "employee__first_name", "employee__last_name"
    )
    rows = [_session_row(session) for session in sessions]
    return {
        "title": REPORT_CHOICES["daily"],
        "subtitle": filters["date"].isoformat(),
        "columns": [
            "Employee",
            "Employee Code",
            "Department",
            "Team",
            "Work Mode",
            "Date",
            "Time In",
            "Time Out",
            "Work Duration",
            "Lunch Duration",
            "Break Duration",
            "Bio Duration",
            "Late Duration",
            "Overbreak Duration",
            "Missing Pairs",
            "Incomplete",
        ],
        "column_keys": [
            "employee_name",
            "employee_code",
            "department",
            "team",
            "work_mode",
            "work_date",
            "first_time_in",
            "last_time_out",
            "total_work_minutes",
            "total_lunch_minutes",
            "total_break_minutes",
            "total_bio_minutes",
            "total_late_minutes",
            "total_overbreak_minutes",
            "missing_tag_pairs_count",
            "has_incomplete_records",
        ],
        "rows": rows,
    }


def _range_summary_report(filters, title, company=None):
    sessions = _base_sessions(filters, company=company)
    grouped = {}
    for session in sessions.order_by("employee__first_name", "employee__last_name", "work_date"):
        key = session.employee_id
        grouped.setdefault(
            key,
            {
                "employee_name": _employee_name(session),
                "employee_code": _employee_code(session),
                "department": _department_name(session),
                "team": _team_name(session),
                "work_mode": session.work_mode or _default_work_mode(session),
                "days_present": 0,
                "total_work_minutes": 0,
                "total_lunch_minutes": 0,
                "total_break_minutes": 0,
                "total_bio_minutes": 0,
                "total_late_minutes": 0,
                "total_overbreak_minutes": 0,
                "missing_tag_pairs_count": 0,
                "incomplete_days": 0,
            },
        )
        row = grouped[key]
        row["days_present"] += 1 if session.first_time_in else 0
        row["total_work_minutes"] += session.total_work_minutes
        row["total_lunch_minutes"] += session.total_lunch_minutes
        row["total_break_minutes"] += session.total_break_minutes
        row["total_bio_minutes"] += session.total_bio_minutes
        row["total_late_minutes"] += session.total_late_minutes
        row["total_overbreak_minutes"] += session.total_overbreak_minutes
        row["missing_tag_pairs_count"] += session.missing_tag_pairs_count
        row["incomplete_days"] += 1 if session.has_incomplete_records else 0

    return {
        "title": title,
        "subtitle": f'{filters["start_date"]} to {filters["end_date"]}',
        "columns": [
            "Employee",
            "Employee Code",
            "Department",
            "Team",
            "Work Mode",
            "Days Present",
            "Work Minutes",
            "Lunch",
            "Break",
            "Bio",
            "Late",
            "Overbreak",
            "Missing Pairs",
            "Incomplete Days",
        ],
        "column_keys": [
            "employee_name",
            "employee_code",
            "department",
            "team",
            "work_mode",
            "days_present",
            "total_work_minutes",
            "total_lunch_minutes",
            "total_break_minutes",
            "total_bio_minutes",
            "total_late_minutes",
            "total_overbreak_minutes",
            "missing_tag_pairs_count",
            "incomplete_days",
        ],
        "rows": list(grouped.values()),
    }


def _overbreak_report(filters, company=None):
    sessions = _base_sessions(filters, company=company)
    overbreaks = OverbreakRecord.objects.select_related(
        "employee",
        "attendance_session",
        "employee__employee_profile",
        "employee__employee_profile__team",
        "employee__employee_profile__department",
        "tag_type",
    ).filter(attendance_session__in=sessions)
    rows = []
    for record in overbreaks.order_by("-created_at"):
        session = record.attendance_session
        rows.append(
            {
                "employee_name": _employee_name(session),
                "employee_code": _employee_code(session),
                "department": _department_name(session),
                "team": _team_name(session),
                "work_mode": session.work_mode or _default_work_mode(session),
                "work_date": session.work_date.isoformat(),
                "tag_type": record.tag_type.name,
                "allowed_minutes": record.allowed_minutes,
                "actual_minutes": record.actual_minutes,
                "excess_minutes": record.excess_minutes,
                "status": record.status,
                "notes": record.notes,
            }
        )
    return {
        "title": REPORT_CHOICES["overbreak"],
        "subtitle": f'{filters["start_date"]} to {filters["end_date"]}',
        "columns": [
            "Employee",
            "Employee Code",
            "Department",
            "Team",
            "Work Mode",
            "Date",
            "Tag Type",
            "Allowed Minutes",
            "Actual Minutes",
            "Excess Minutes",
            "Status",
            "Notes",
        ],
        "column_keys": [
            "employee_name",
            "employee_code",
            "department",
            "team",
            "work_mode",
            "work_date",
            "tag_type",
            "allowed_minutes",
            "actual_minutes",
            "excess_minutes",
            "status",
            "notes",
        ],
        "rows": rows,
    }


def _missed_logs_report(filters, company=None):
    sessions = _base_sessions(filters, company=company).filter(
        has_incomplete_records=True
    ).order_by("work_date", "employee__first_name", "employee__last_name")
    rows = []
    for session in sessions:
        rows.append(
            {
                "employee_name": _employee_name(session),
                "employee_code": _employee_code(session),
                "department": _department_name(session),
                "team": _team_name(session),
                "work_mode": session.work_mode or _default_work_mode(session),
                "work_date": session.work_date.isoformat(),
                "missing_tag_pairs_count": session.missing_tag_pairs_count,
                "summary_notes": ", ".join(session.summary_notes),
            }
        )
    return {
        "title": REPORT_CHOICES["missed"],
        "subtitle": f'{filters["start_date"]} to {filters["end_date"]}',
        "columns": [
            "Employee",
            "Employee Code",
            "Department",
            "Team",
            "Work Mode",
            "Date",
            "Missing Tag Pairs",
            "Summary Notes",
        ],
        "column_keys": [
            "employee_name",
            "employee_code",
            "department",
            "team",
            "work_mode",
            "work_date",
            "missing_tag_pairs_count",
            "summary_notes",
        ],
        "rows": rows,
    }


def _late_undertime_report(filters, company=None):
    sessions = _base_sessions(filters, company=company)
    required_work_minutes = _required_work_minutes()
    rows = []
    for session in sessions.order_by("work_date", "employee__first_name", "employee__last_name"):
        undertime_minutes = max(0, required_work_minutes - session.total_work_minutes)
        if session.total_late_minutes == 0 and undertime_minutes == 0:
            continue
        rows.append(
            {
                "employee_name": _employee_name(session),
                "employee_code": _employee_code(session),
                "department": _department_name(session),
                "team": _team_name(session),
                "work_mode": session.work_mode or _default_work_mode(session),
                "work_date": session.work_date.isoformat(),
                "late_minutes": session.total_late_minutes,
                "undertime_minutes": undertime_minutes,
                "total_work_minutes": session.total_work_minutes,
            }
        )
    return {
        "title": REPORT_CHOICES["late-undertime"],
        "subtitle": f'{filters["start_date"]} to {filters["end_date"]}',
        "columns": [
            "Employee",
            "Employee Code",
            "Department",
            "Team",
            "Work Mode",
            "Date",
            "Late Minutes",
            "Undertime Minutes",
            "Total Work Minutes",
        ],
        "column_keys": [
            "employee_name",
            "employee_code",
            "department",
            "team",
            "work_mode",
            "work_date",
            "late_minutes",
            "undertime_minutes",
            "total_work_minutes",
        ],
        "rows": rows,
    }


def _session_row(session):
    return {
        "employee_name": _employee_name(session),
        "employee_code": _employee_code(session),
        "department": _department_name(session),
        "team": _team_name(session),
        "work_mode": session.work_mode or _default_work_mode(session),
        "work_date": session.work_date.isoformat(),
        "first_time_in": _format_datetime(session.first_time_in),
        "last_time_out": _format_datetime(session.last_time_out),
        "total_work_minutes": _format_duration_minutes(session.total_work_minutes),
        "total_lunch_minutes": _format_duration_minutes(session.total_lunch_minutes),
        "total_break_minutes": _format_duration_minutes(session.total_break_minutes),
        "total_bio_minutes": _format_duration_minutes(session.total_bio_minutes),
        "total_late_minutes": _format_duration_minutes(session.total_late_minutes),
        "total_overbreak_minutes": _format_duration_minutes(session.total_overbreak_minutes),
        "missing_tag_pairs_count": session.missing_tag_pairs_count,
        "has_incomplete_records": "Yes" if session.has_incomplete_records else "No",
    }


def _employee_name(session):
    return session.employee.get_full_name() or session.employee.username


def _employee_code(session):
    profile = getattr(session.employee, "employee_profile", None)
    return profile.employee_code if profile else "-"


def _department_name(session):
    profile = getattr(session.employee, "employee_profile", None)
    if not profile:
        return "-"
    department = profile.department or getattr(profile.team, "department", None)
    return department.name if department else "-"


def _team_name(session):
    profile = getattr(session.employee, "employee_profile", None)
    return profile.team.name if profile and profile.team else "-"


def _default_work_mode(session):
    profile = getattr(session.employee, "employee_profile", None)
    return profile.default_work_mode if profile else "-"


def _format_datetime(value):
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %I:%M %p")


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _required_work_minutes():
    settings = SystemSetting.objects.order_by("-updated_at").first()
    return getattr(settings, "required_work_minutes", DEFAULT_REQUIRED_WORK_MINUTES) if settings else DEFAULT_REQUIRED_WORK_MINUTES


def _format_duration_minutes(minutes):
    total_seconds = int((minutes or 0) * 60)
    hours = total_seconds // 3600
    remainder = total_seconds % 3600
    mins = remainder // 60
    secs = remainder % 60
    return f"{hours:02d}:{mins:02d}:{secs:02d}"
