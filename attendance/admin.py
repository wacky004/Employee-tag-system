from django.contrib import admin

from .models import AttendanceSession, CorrectionRequest, OverbreakRecord


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "work_date",
        "first_time_in",
        "last_time_out",
        "total_work_minutes",
        "total_lunch_minutes",
        "total_break_minutes",
        "total_bio_minutes",
        "total_overbreak_minutes",
        "missing_tag_pairs_count",
        "has_incomplete_records",
        "is_late",
    )
    list_filter = ("current_status", "is_late", "has_incomplete_records", "work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    readonly_fields = ("summary_notes",)


@admin.register(OverbreakRecord)
class OverbreakRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "tag_type", "work_date", "excess_minutes", "status")
    list_filter = ("status", "tag_type")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")

    def work_date(self, obj):
        return obj.attendance_session.work_date


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "request_type", "target_work_date", "requested_tag_type", "status", "reviewed_by", "created_at")
    list_filter = ("request_type", "status", "target_work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "reason", "details")
    readonly_fields = ("reviewed_at", "applied_tag_log")
