from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from core.models import SystemSetting
from tagging.models import TagLog, TagType

from .models import AttendanceSession, OverbreakRecord


CATEGORY_DURATION_FIELDS = {
    TagType.Category.LUNCH: "total_lunch_minutes",
    TagType.Category.BREAK: "total_break_minutes",
    TagType.Category.BIO: "total_bio_minutes",
}

CATEGORY_STATUS = {
    TagType.Category.LUNCH: AttendanceSession.Status.LUNCH,
    TagType.Category.BREAK: AttendanceSession.Status.BREAK,
    TagType.Category.BIO: AttendanceSession.Status.BIO,
}

ALLOWED_MINUTES_FIELDS = {
    TagType.Category.LUNCH: "lunch_minutes_allowed",
    TagType.Category.BREAK: "break_minutes_allowed",
    TagType.Category.BIO: "bio_minutes_allowed",
}


def build_daily_summary(employee, work_date):
    logs = list(
        TagLog.objects.select_related("tag_type")
        .filter(employee=employee, work_date=work_date)
        .order_by("timestamp", "id")
    )

    defaults = {
        "first_time_in": None,
        "last_time_out": None,
        "current_status": AttendanceSession.Status.OFF_DUTY,
        "work_mode": "",
        "timezone_at_log": _get_default_timezone_name(),
        "total_work_minutes": 0,
        "total_lunch_minutes": 0,
        "total_break_minutes": 0,
        "total_bio_minutes": 0,
        "total_overbreak_minutes": 0,
        "total_late_minutes": 0,
        "is_late": False,
        "missing_tag_pairs_count": 0,
        "has_incomplete_records": False,
        "summary_notes": [],
        "remarks": "",
    }
    if not logs:
        defaults["remarks"] = "No tag logs found for this work date."
        return defaults, []

    settings = SystemSetting.objects.order_by("-updated_at").first()
    open_intervals = {
        TagType.Category.LUNCH: None,
        TagType.Category.BREAK: None,
        TagType.Category.BIO: None,
    }
    overbreaks = []
    notes = []

    last_status = AttendanceSession.Status.OFF_DUTY

    for log in logs:
        tag_type = log.tag_type
        code = tag_type.code

        if code == "TIME_IN":
            if defaults["first_time_in"] is None:
                defaults["first_time_in"] = log.timestamp
                defaults["work_mode"] = log.work_mode
                defaults["timezone_at_log"] = _detect_timezone_name(log, settings)
            last_status = AttendanceSession.Status.WORKING
            continue

        if code == "TIME_OUT":
            defaults["last_time_out"] = log.timestamp
            last_status = AttendanceSession.Status.OFF_DUTY
            continue

        category = tag_type.category
        if category not in open_intervals:
            continue

        if tag_type.direction == TagType.Direction.OUT:
            if open_intervals[category] is not None:
                notes.append(f"Missing {category.lower()} return before another {category.lower()} out.")
            open_intervals[category] = log
            last_status = CATEGORY_STATUS[category]
            continue

        if open_intervals[category] is None:
            notes.append(f"{category.title()} in has no matching {category.lower()} out.")
            last_status = AttendanceSession.Status.WORKING
            continue

        out_log = open_intervals[category]
        duration_minutes = _duration_minutes(out_log.timestamp, log.timestamp)
        field_name = CATEGORY_DURATION_FIELDS[category]
        defaults[field_name] += duration_minutes

        allowed_minutes = _allowed_minutes_for(category, tag_type, settings)
        excess_minutes = max(0, duration_minutes - allowed_minutes)
        if excess_minutes > 0:
            defaults["total_overbreak_minutes"] += excess_minutes
            overbreaks.append(
                {
                    "employee": employee,
                    "tag_type": out_log.tag_type,
                    "started_at": out_log.timestamp,
                    "ended_at": log.timestamp,
                    "allowed_minutes": allowed_minutes,
                    "actual_minutes": duration_minutes,
                    "excess_minutes": excess_minutes,
                    "notes": f"{category.title()} exceeded by {excess_minutes} minute(s).",
                }
            )

        open_intervals[category] = None
        last_status = AttendanceSession.Status.WORKING

    for category, open_log in open_intervals.items():
        if open_log is not None:
            notes.append(f"Missing {category.lower()} in for {category.lower()} out.")

    if defaults["first_time_in"] and defaults["last_time_out"]:
        gross_minutes = _duration_minutes(defaults["first_time_in"], defaults["last_time_out"])
        non_work_minutes = (
            defaults["total_lunch_minutes"]
            + defaults["total_break_minutes"]
            + defaults["total_bio_minutes"]
        )
        defaults["total_work_minutes"] = max(0, gross_minutes - non_work_minutes)
    elif defaults["first_time_in"] or defaults["last_time_out"]:
        notes.append("Incomplete shift pair. Missing time in or time out.")

    late_minutes = _calculate_late_minutes(defaults["first_time_in"], settings)
    defaults["total_late_minutes"] = late_minutes
    defaults["is_late"] = late_minutes > 0
    defaults["missing_tag_pairs_count"] = len(notes)
    defaults["has_incomplete_records"] = bool(notes)
    defaults["summary_notes"] = notes
    defaults["current_status"] = last_status
    defaults["remarks"] = "; ".join(notes) if notes else "Attendance summary calculated."
    return defaults, overbreaks


@transaction.atomic
def refresh_attendance_session(employee, work_date):
    summary, overbreaks = build_daily_summary(employee, work_date)
    session, _ = AttendanceSession.objects.update_or_create(
        employee=employee,
        work_date=work_date,
        defaults=summary,
    )
    _sync_overbreak_records(session, overbreaks)
    return session


def _sync_overbreak_records(session, overbreaks):
    session.overbreak_records.filter(status=OverbreakRecord.Status.OPEN).delete()
    if not overbreaks:
        return

    OverbreakRecord.objects.bulk_create(
        [
            OverbreakRecord(
                employee=session.employee,
                attendance_session=session,
                tag_type=item["tag_type"],
                started_at=item["started_at"],
                ended_at=item["ended_at"],
                allowed_minutes=item["allowed_minutes"],
                actual_minutes=item["actual_minutes"],
                excess_minutes=item["excess_minutes"],
                notes=item["notes"],
            )
            for item in overbreaks
        ]
    )


def _duration_minutes(start_at, end_at):
    if not start_at or not end_at or end_at <= start_at:
        return 0
    return int((end_at - start_at).total_seconds() // 60)


def _allowed_minutes_for(category, tag_type, settings):
    if tag_type.default_allowed_minutes is not None:
        return tag_type.default_allowed_minutes
    if settings is None:
        return 0
    return getattr(settings, ALLOWED_MINUTES_FIELDS[category], 0)


def _calculate_late_minutes(first_time_in, settings):
    if not first_time_in or settings is None or settings.late_after_time is None:
        return 0

    tz_name = settings.default_timezone or timezone.get_current_timezone_name()
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tzinfo = timezone.get_current_timezone()

    local_first_in = timezone.localtime(first_time_in, tzinfo)
    late_threshold = datetime.combine(local_first_in.date(), settings.late_after_time, tzinfo=tzinfo)
    if local_first_in <= late_threshold:
        return 0
    return int((local_first_in - late_threshold).total_seconds() // 60)


def _detect_timezone_name(log, settings):
    if log.metadata.get("timezone"):
        return log.metadata["timezone"]
    if settings and settings.default_timezone:
        return settings.default_timezone
    return _get_default_timezone_name()


def _get_default_timezone_name():
    return timezone.get_current_timezone_name()
