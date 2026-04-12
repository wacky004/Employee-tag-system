from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from core.models import SystemSetting
from tagging.models import TagLog, TagType

from .models import AttendanceSession, OverbreakRecord

CURRENT_STATUS_LABELS = {
    AttendanceSession.Status.OFF_DUTY: "Timed Out",
    AttendanceSession.Status.WORKING: "Currently Working",
    AttendanceSession.Status.LUNCH: "On Lunch",
    AttendanceSession.Status.BREAK: "On Break",
    AttendanceSession.Status.BIO: "On Bio",
}


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

CATEGORY_CODE_MAP = {
    "lunch": (TagType.Category.LUNCH, "LUNCH_OUT", "LUNCH_IN"),
    "break": (TagType.Category.BREAK, "BREAK_OUT", "BREAK_IN"),
    "bio": (TagType.Category.BIO, "BIO_OUT", "BIO_IN"),
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

    late_minutes = _calculate_late_minutes(employee, defaults["first_time_in"], settings)
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


def get_valid_tag_codes(employee, work_date):
    state = get_employee_tagging_state(employee, work_date)
    return tuple(state["valid_codes"])


@transaction.atomic
def create_employee_tag(employee, tag_code, work_date=None):
    work_date = work_date or timezone.localdate()
    state = get_employee_tagging_state(employee, work_date)
    valid_codes = state["valid_codes"]
    if tag_code not in valid_codes:
        raise ValueError("This tagging action is not valid right now.")

    tag_type = TagType.objects.filter(code=tag_code, is_active=True).first()
    if tag_type is None:
        raise ValueError("The requested tag type is not configured.")

    latest_session = AttendanceSession.objects.filter(
        employee=employee,
        work_date=work_date,
    ).first()
    employee_profile = _get_employee_profile(employee)

    work_mode = ""
    if tag_code == "TIME_IN":
        work_mode = employee_profile.default_work_mode if employee_profile else ""
    elif latest_session and latest_session.work_mode:
        work_mode = latest_session.work_mode
    elif employee_profile:
        work_mode = employee_profile.default_work_mode

    tag_log = TagLog.objects.create(
        employee=employee,
        tag_type=tag_type,
        work_date=work_date,
        timestamp=timezone.now(),
        work_mode=work_mode,
        source=TagLog.Source.WEB,
        created_by=employee,
    )
    session = refresh_attendance_session(employee, work_date)
    return tag_log, session


def get_current_status_label(session):
    if session is None or not session.first_time_in:
        return "Not Tagged Yet"
    return CURRENT_STATUS_LABELS.get(session.current_status, "Unknown")


def get_employee_tagging_state(employee, work_date):
    logs = list(
        TagLog.objects.select_related("tag_type")
        .filter(employee=employee, work_date=work_date)
        .order_by("timestamp", "id")
    )
    session = AttendanceSession.objects.filter(employee=employee, work_date=work_date).first()
    settings = SystemSetting.objects.order_by("-updated_at").first()
    open_states = {"lunch": None, "break": None, "bio": None}

    for log in logs:
        for key, (category, start_code, end_code) in CATEGORY_CODE_MAP.items():
            if log.tag_type.code == start_code:
                open_states[key] = log
            elif log.tag_type.code == end_code:
                open_states[key] = None

    has_time_in = bool(session and session.first_time_in and not session.last_time_out)
    has_time_out = bool(session and session.last_time_out)
    cooldown_active = False
    cooldown_remaining_seconds = 0
    latest_time_out_log = next((log for log in reversed(logs) if log.tag_type.code == "TIME_OUT"), None)
    cooldown_hours = settings.time_in_cooldown_hours if settings else SystemSetting._meta.get_field("time_in_cooldown_hours").get_default()
    if latest_time_out_log and cooldown_hours:
        cooldown_end = latest_time_out_log.timestamp + timezone.timedelta(hours=cooldown_hours)
        if timezone.now() < cooldown_end:
            cooldown_active = True
            cooldown_remaining_seconds = max(0, int((cooldown_end - timezone.now()).total_seconds()))

    valid_codes = []
    if not logs:
        valid_codes.append("TIME_IN")
    elif has_time_out and not cooldown_active:
        valid_codes.append("TIME_IN")
    if has_time_in:
        valid_codes.append("TIME_OUT")
        for key, (_, start_code, end_code) in CATEGORY_CODE_MAP.items():
            valid_codes.append(end_code if open_states[key] else start_code)

    controls = {}
    now = timezone.now()
    for key, (category, start_code, end_code) in CATEGORY_CODE_MAP.items():
        allowed_minutes = _allowed_minutes_for_category(category, settings)
        consumed_minutes = _get_consumed_minutes(session, category)
        active_log = open_states[key]
        active_elapsed = _duration_minutes(active_log.timestamp, now) if active_log else 0
        remaining_minutes = max(0, allowed_minutes - consumed_minutes - active_elapsed)
        controls[key] = {
            "key": key,
            "label": key.title(),
            "code": end_code if active_log else start_code,
            "button_label": f"{key.title()} End" if active_log else f"{key.title()} Start",
            "active": bool(active_log),
            "started_at": active_log.timestamp if active_log else None,
            "allowed_minutes": allowed_minutes,
            "consumed_minutes": consumed_minutes,
            "active_elapsed_minutes": active_elapsed,
            "remaining_minutes": remaining_minutes,
            "remaining_seconds": max(0, remaining_minutes * 60),
        }

    latest_log = logs[-1] if logs else None
    return {
        "logs": logs,
        "session": session,
        "valid_codes": valid_codes,
        "controls": controls,
        "latest_log": latest_log,
        "has_time_in": has_time_in,
        "has_time_out": has_time_out,
        "cooldown_active": cooldown_active,
        "cooldown_remaining_seconds": cooldown_remaining_seconds,
        "cooldown_hours": cooldown_hours,
    }


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


def _allowed_minutes_for_category(category, settings):
    if settings is None:
        return 0
    return getattr(settings, ALLOWED_MINUTES_FIELDS[category], 0)


def _calculate_late_minutes(employee, first_time_in, settings):
    if not first_time_in:
        return 0

    employee_profile = _get_employee_profile(employee)
    if employee_profile and employee_profile.schedule_start_time:
        schedule_time = employee_profile.schedule_start_time
    elif settings is not None and settings.late_after_time is not None:
        schedule_time = settings.late_after_time
    else:
        return 0

    tz_name = (
        employee_profile.timezone
        if employee_profile and employee_profile.timezone
        else settings.default_timezone if settings else timezone.get_current_timezone_name()
    )
    try:
        tzinfo = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tzinfo = timezone.get_current_timezone()

    local_first_in = timezone.localtime(first_time_in, tzinfo)
    late_threshold = datetime.combine(local_first_in.date(), schedule_time, tzinfo=tzinfo)
    grace_minutes = settings.late_grace_minutes if settings else 0
    if grace_minutes:
        late_threshold = late_threshold + timezone.timedelta(minutes=grace_minutes)
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


def _get_employee_profile(employee):
    try:
        return employee.employee_profile
    except ObjectDoesNotExist:
        return None


def _get_consumed_minutes(session, category):
    if not session:
        return 0
    field_map = {
        TagType.Category.LUNCH: session.total_lunch_minutes,
        TagType.Category.BREAK: session.total_break_minutes,
        TagType.Category.BIO: session.total_bio_minutes,
    }
    return field_map.get(category, 0)
