from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from .forms import EmployeeForm, EquipmentAssignmentForm, EquipmentCategoryForm, EquipmentForm, SupervisorForm
from .models import Employee, Equipment, EquipmentAssignment, EquipmentCategory, EquipmentHistoryLog, Supervisor

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
        form_map = {
            "create_supervisor": ("supervisor_form", SupervisorForm, "Supervisor added successfully."),
            "create_employee": ("employee_form", EmployeeForm, "Employee record created successfully."),
            "create_category": ("category_form", EquipmentCategoryForm, "Equipment category created successfully."),
            "create_equipment": ("equipment_form", EquipmentForm, "Equipment record created successfully."),
        }

        if action in form_map:
            context_key, form_class, success_message = form_map[action]
            form = form_class(request.POST, prefix=context_key.split("_")[0])
            if form.is_valid():
                form.save()
                messages.success(request, success_message)
                return redirect("inventory:dashboard")
            return self.render_to_response(self.get_context_data(**{context_key: form}))

        if action == "assign_equipment":
            form = EquipmentAssignmentForm(request.POST, prefix="assignment")
            if form.is_valid():
                self._assign_equipment(
                    equipment=form.cleaned_data["equipment"],
                    employee=form.cleaned_data["employee"],
                    assigned_by=request.user,
                    remarks=form.cleaned_data["remarks"],
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
        selected_employee_id = self.request.GET.get("employee", "").strip()
        selected_equipment_id = self.request.GET.get("equipment", "").strip()

        employees = Employee.objects.select_related("supervisor").order_by("full_name", "employee_code")
        if query:
            employees = employees.filter(
                Q(full_name__icontains=query)
                | Q(employee_code__icontains=query)
                | Q(job_title__icontains=query)
                | Q(department__icontains=query)
                | Q(team_name__icontains=query)
                | Q(supervisor__full_name__icontains=query)
            )

        supervisors = list(
            Supervisor.objects.annotate(member_count=Count("employees")).order_by("full_name")
        )
        selected_employee = None
        if selected_employee_id:
            selected_employee = Employee.objects.select_related("supervisor").filter(pk=selected_employee_id).first()
        elif query:
            selected_employee = employees.first()

        equipment_list = Equipment.objects.select_related("category", "current_employee").order_by("asset_code", "name")
        selected_equipment = None
        if selected_equipment_id:
            selected_equipment = equipment_list.filter(pk=selected_equipment_id).first()

        summary_counts = {status: 0 for status, _label in Equipment.Status.choices}
        for row in equipment_list.values("status").annotate(total=Count("id")):
            summary_counts[row["status"]] = row["total"]

        context.update(
            {
                "supervisor_form": kwargs.get("supervisor_form") or SupervisorForm(prefix="supervisor"),
                "employee_form": kwargs.get("employee_form") or EmployeeForm(prefix="employee"),
                "category_form": kwargs.get("category_form") or EquipmentCategoryForm(prefix="category"),
                "equipment_form": kwargs.get("equipment_form") or EquipmentForm(prefix="equipment"),
                "assignment_form": kwargs.get("assignment_form") or EquipmentAssignmentForm(prefix="assignment"),
                "supervisors": supervisors,
                "employees": list(employees),
                "equipment_list": list(equipment_list),
                "equipment_categories": list(EquipmentCategory.objects.order_by("name")),
                "recent_assignments": list(
                    EquipmentAssignment.objects.select_related("equipment", "employee", "assigned_by")[:10]
                ),
                "selected_employee": selected_employee,
                "selected_employee_current_equipment": list(
                    Equipment.objects.filter(current_employee=selected_employee).order_by("asset_code", "name")
                ) if selected_employee else [],
                "selected_employee_history": list(
                    EquipmentAssignment.objects.select_related("equipment", "assigned_by")
                    .filter(employee=selected_employee)
                ) if selected_employee else [],
                "selected_equipment": selected_equipment,
                "selected_equipment_history": list(
                    EquipmentHistoryLog.objects.select_related("employee", "assignment")
                    .filter(equipment=selected_equipment)
                ) if selected_equipment else [],
                "query": query,
                "selected_employee_id": selected_employee_id,
                "selected_equipment_id": selected_equipment_id,
                "can_manage_inventory": self.request.user.role == User.Role.SUPER_ADMIN,
                "status_cards": [
                    {"code": code, "label": label, "total": summary_counts.get(code, 0)}
                    for code, label in Equipment.Status.choices
                ],
            }
        )
        return context

    def _assign_equipment(self, equipment, employee, assigned_by, remarks, status):
        open_assignment = equipment.assignments.filter(returned_at__isnull=True).first()
        now = timezone.now()

        if open_assignment:
            open_assignment.returned_at = now
            open_assignment.save(update_fields=["returned_at"])
            EquipmentHistoryLog.objects.create(
                equipment=equipment,
                employee=open_assignment.employee,
                assignment=open_assignment,
                action=EquipmentHistoryLog.Action.RETURNED,
                status_snapshot=equipment.status,
                remarks="Automatically closed before reassignment.",
            )

        assignment = EquipmentAssignment.objects.create(
            equipment=equipment,
            employee=employee,
            assigned_by=assigned_by,
            remarks=remarks,
            assigned_at=now,
        )

        equipment.current_employee = employee
        equipment.last_assigned_at = now
        update_fields = ["current_employee", "last_assigned_at"]
        if status:
            equipment.status = status
            update_fields.append("status")
        equipment.save(update_fields=update_fields)

        EquipmentHistoryLog.objects.create(
            equipment=equipment,
            employee=employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.ASSIGNED,
            status_snapshot=equipment.status,
            remarks=remarks,
        )

        if status:
            EquipmentHistoryLog.objects.create(
                equipment=equipment,
                employee=employee,
                assignment=assignment,
                action=EquipmentHistoryLog.Action.STATUS_CHANGED,
                status_snapshot=equipment.status,
                remarks="Equipment status updated during assignment.",
            )
