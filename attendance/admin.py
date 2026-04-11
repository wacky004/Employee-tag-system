from django.contrib import admin

from .models import AttendanceSession, CorrectionRequest, OverbreakRecord


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("employee", "work_date", "current_status", "is_late", "total_work_minutes")
    list_filter = ("current_status", "is_late", "work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")


@admin.register(OverbreakRecord)
class OverbreakRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "tag_type", "work_date", "excess_minutes", "status")
    list_filter = ("status", "tag_type")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")

    def work_date(self, obj):
        return obj.attendance_session.work_date


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "request_type", "target_work_date", "status", "created_at")
    list_filter = ("request_type", "status", "target_work_date")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name", "details")
