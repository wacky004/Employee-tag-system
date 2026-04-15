from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from .forms import EquipmentAssignmentForm, EquipmentForm, InventorySupervisorForm, InventoryUserForm
from .models import Equipment, EquipmentAssignment, InventoryUser

User = get_user_model()


def _dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


class InventoryAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(_dashboard_url(self.request.user))
        return super().handle_no_permission()


class InventoryDashboardView(InventoryAccessMixin, TemplateView):
    template_name = "inventory/dashboard.html"

    def post(self, request, *args, **kwargs):
        if request.user.role != User.Role.SUPER_ADMIN:
            messages.error(request, "Only super admins can manage inventory records.")
            return redirect("inventory:dashboard")

        action = request.POST.get("inventory_action", "").strip()
        if action == "create_supervisor":
            form = InventorySupervisorForm(request.POST, prefix="supervisor")
            if form.is_valid():
                form.save()
                messages.success(request, "Supervisor added to inventory management.")
                return redirect("inventory:dashboard")
            return self.render_to_response(self.get_context_data(supervisor_form=form))

        if action == "create_user":
            form = InventoryUserForm(request.POST, prefix="user")
            if form.is_valid():
                form.save()
                messages.success(request, "Inventory employee added successfully.")
                return redirect("inventory:dashboard")
            return self.render_to_response(self.get_context_data(user_form=form))

        if action == "create_equipment":
            form = EquipmentForm(request.POST, prefix="equipment")
            if form.is_valid():
                form.save()
                messages.success(request, "Equipment record created.")
                return redirect("inventory:dashboard")
            return self.render_to_response(self.get_context_data(equipment_form=form))

        if action == "assign_equipment":
            form = EquipmentAssignmentForm(request.POST, prefix="assignment")
            if form.is_valid():
                self._assign_equipment(
                    equipment=form.cleaned_data["equipment"],
                    holder=form.cleaned_data["holder"],
                    assigned_by=request.user,
                    notes=form.cleaned_data["notes"],
                    status=form.cleaned_data["status"],
                )
                messages.success(request, "Equipment assigned successfully.")
                return redirect("inventory:dashboard")
            return self.render_to_response(self.get_context_data(assignment_form=form))

        messages.error(request, "Unknown inventory action.")
        return redirect("inventory:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        selected_user_id = self.request.GET.get("user", "").strip()
        selected_equipment_id = self.request.GET.get("equipment", "").strip()

        inventory_users = InventoryUser.objects.select_related("supervisor").order_by(
            "-is_supervisor",
            "full_name",
            "employee_code",
        )
        if query:
            inventory_users = inventory_users.filter(
                Q(full_name__icontains=query)
                | Q(employee_code__icontains=query)
                | Q(job_title__icontains=query)
                | Q(department_name__icontains=query)
                | Q(team_name__icontains=query)
            )

        supervisors = list(
            InventoryUser.objects.filter(is_supervisor=True).annotate(
                member_count=Count("team_members")
            ).order_by("full_name")
        )
        selected_user = None
        if selected_user_id:
            selected_user = InventoryUser.objects.filter(pk=selected_user_id).first()
        elif query:
            selected_user = inventory_users.first()

        selected_equipment = None
        if selected_equipment_id:
            selected_equipment = Equipment.objects.select_related("current_holder").filter(pk=selected_equipment_id).first()

        equipment_qs = Equipment.objects.select_related("current_holder").order_by("asset_code", "name")
        summary_counts = {status: 0 for status, _label in Equipment.Status.choices}
        for row in equipment_qs.values("status").annotate(total=Count("id")):
            summary_counts[row["status"]] = row["total"]

        context.update(
            {
                "supervisor_form": kwargs.get("supervisor_form") or InventorySupervisorForm(prefix="supervisor"),
                "user_form": kwargs.get("user_form") or InventoryUserForm(prefix="user"),
                "equipment_form": kwargs.get("equipment_form") or EquipmentForm(prefix="equipment"),
                "assignment_form": kwargs.get("assignment_form") or EquipmentAssignmentForm(prefix="assignment"),
                "inventory_users": list(inventory_users),
                "supervisors": supervisors,
                "equipment_list": list(equipment_qs),
                "recent_assignments": list(
                    EquipmentAssignment.objects.select_related("equipment", "holder", "assigned_by")[:10]
                ),
                "selected_user": selected_user,
                "selected_user_current_equipment": list(
                    Equipment.objects.filter(current_holder=selected_user).order_by("asset_code", "name")
                ) if selected_user else [],
                "selected_user_history": list(
                    EquipmentAssignment.objects.select_related("equipment", "assigned_by")
                    .filter(holder=selected_user)
                ) if selected_user else [],
                "selected_equipment": selected_equipment,
                "selected_equipment_history": list(
                    EquipmentAssignment.objects.select_related("holder", "assigned_by")
                    .filter(equipment=selected_equipment)
                ) if selected_equipment else [],
                "query": query,
                "selected_user_id": selected_user_id,
                "selected_equipment_id": selected_equipment_id,
                "can_manage_inventory": self.request.user.role == User.Role.SUPER_ADMIN,
                "status_cards": [
                    {"code": code, "label": label, "total": summary_counts.get(code, 0)}
                    for code, label in Equipment.Status.choices
                ],
            }
        )
        return context

    def _assign_equipment(self, equipment, holder, assigned_by, notes, status):
        open_assignment = equipment.assignments.filter(returned_at__isnull=True).first()
        now = timezone.now()
        if open_assignment:
            open_assignment.returned_at = now
            if notes:
                open_assignment.notes = (
                    f"{open_assignment.notes}\nClosed automatically before reassignment.".strip()
                )
            open_assignment.save(update_fields=["returned_at", "notes"])

        EquipmentAssignment.objects.create(
            equipment=equipment,
            holder=holder,
            assigned_by=assigned_by,
            notes=notes,
            assigned_at=now,
        )
        equipment.current_holder = holder
        equipment.last_assigned_at = now
        if status:
            equipment.status = status
            equipment.save(update_fields=["current_holder", "last_assigned_at", "status"])
            return
        equipment.save(update_fields=["current_holder", "last_assigned_at"])
