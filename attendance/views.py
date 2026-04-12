from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView, TemplateView

from accounts.views import RoleRequiredMixin
from auditlogs.services import create_audit_log
from tagging.models import TagLog

from .forms import CorrectionRequestForm, CorrectionReviewForm
from .models import AttendanceSession, CorrectionRequest
from .services import refresh_attendance_session

User = get_user_model()


class CorrectionRequestCreateView(RoleRequiredMixin, FormView):
    template_name = "attendance/corrections.html"
    form_class = CorrectionRequestForm
    allowed_roles = (User.Role.EMPLOYEE, User.Role.ADMIN, User.Role.SUPER_ADMIN)

    def form_valid(self, form):
        correction = form.save(commit=False)
        correction.employee = self.request.user
        correction.attendance_session = AttendanceSession.objects.filter(
            employee=self.request.user,
            work_date=correction.target_work_date,
        ).first()
        correction.save()
        create_audit_log(
            actor=self.request.user,
            employee=self.request.user,
            action="CORRECTION_REQUEST_SUBMITTED",
            target_model="CorrectionRequest",
            target_id=correction.id,
            description="Employee submitted a correction request.",
            changes={
                "request_type": correction.request_type,
                "requested_tag_type": correction.requested_tag_type.code if correction.requested_tag_type else "",
                "requested_timestamp": correction.requested_timestamp.isoformat() if correction.requested_timestamp else "",
                "reason": correction.reason,
            },
        )
        messages.success(self.request, "Correction request submitted.")
        return redirect("attendance:corrections")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["my_requests"] = CorrectionRequest.objects.filter(employee=self.request.user).select_related(
            "requested_tag_type", "reviewed_by"
        )
        return context


class CorrectionReviewListView(RoleRequiredMixin, TemplateView):
    template_name = "attendance/correction_review.html"
    allowed_roles = (User.Role.ADMIN, User.Role.SUPER_ADMIN)

    def post(self, request, *args, **kwargs):
        correction = get_object_or_404(CorrectionRequest, pk=request.POST.get("correction_id"))
        form = CorrectionReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid review submission.")
            return redirect("attendance:correction-review")

        decision = form.cleaned_data["decision"]
        resolution_notes = form.cleaned_data["resolution_notes"]
        correction.reviewed_by = request.user
        correction.reviewed_at = timezone.now()
        correction.resolution_notes = resolution_notes

        if decision == "approve":
            correction.status = CorrectionRequest.Status.APPROVED
            tag_log = self._apply_correction(correction, request.user, resolution_notes)
            correction.applied_tag_log = tag_log
            action = "CORRECTION_REQUEST_APPROVED"
            description = "Admin approved a correction request."
        else:
            correction.status = CorrectionRequest.Status.REJECTED
            action = "CORRECTION_REQUEST_REJECTED"
            description = "Admin rejected a correction request."

        correction.save()
        create_audit_log(
            actor=request.user,
            employee=correction.employee,
            action=action,
            target_model="CorrectionRequest",
            target_id=correction.id,
            description=description,
            changes={
                "status": correction.status,
                "resolution_notes": correction.resolution_notes,
                "applied_tag_log_id": correction.applied_tag_log_id or "",
            },
            metadata={"reason": correction.reason},
        )
        messages.success(request, f"Correction request {decision}d.")
        return redirect("attendance:correction-review")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["review_form"] = CorrectionReviewForm()
        context["pending_requests"] = CorrectionRequest.objects.filter(
            status=CorrectionRequest.Status.PENDING
        ).select_related("employee", "requested_tag_type", "attendance_session")
        context["reviewed_requests"] = CorrectionRequest.objects.exclude(
            status=CorrectionRequest.Status.PENDING
        ).select_related("employee", "requested_tag_type", "reviewed_by", "applied_tag_log")[:20]
        return context

    def _apply_correction(self, correction, actor, resolution_notes):
        tag_log = None
        if correction.requested_tag_type and correction.requested_timestamp:
            tag_log = TagLog.objects.create(
                employee=correction.employee,
                tag_type=correction.requested_tag_type,
                work_date=correction.target_work_date,
                timestamp=correction.requested_timestamp,
                work_mode=correction.requested_work_mode,
                source=TagLog.Source.CORRECTION,
                notes=correction.reason,
                metadata={
                    "resolution_notes": resolution_notes,
                    "correction_request_id": correction.id,
                },
                created_by=actor,
            )
            create_audit_log(
                actor=actor,
                employee=correction.employee,
                action="TAG_LOG_CREATED_FROM_CORRECTION",
                target_model="TagLog",
                target_id=tag_log.id,
                description="Created tag log from approved correction request.",
                changes={
                    "tag_type": tag_log.tag_type.code,
                    "timestamp": tag_log.timestamp.isoformat(),
                    "source": tag_log.source,
                },
                metadata={"reason": correction.reason},
            )
            refresh_attendance_session(correction.employee, correction.target_work_date)
        return tag_log
