from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from .forms import (
    EquipmentAssignmentCreateForm,
    EmployeeAssignSupervisorForm,
    EmployeeForm,
    EquipmentAssignmentForm,
    EquipmentCategoryForm,
    EquipmentForm,
    EquipmentReturnForm,
    SupervisorForm,
)
from .models import Employee, Equipment, EquipmentAssignment, EquipmentCategory, EquipmentHistoryLog, Supervisor

User = get_user_model()


def _dashboard_url(user):
    if user.role == User.Role.SUPER_ADMIN:
        return reverse("accounts:super-admin-dashboard")
    if user.role == User.Role.ADMIN:
        return reverse("accounts:manager-dashboard")
    return reverse("accounts:employee-dashboard")


def _build_assignment_history(equipment):
    assignment_history = []
    assignments = equipment.assignments.select_related("employee", "assigned_by").order_by("-assigned_at", "-id")
    for assignment in assignments:
        assigned_log = assignment.history_logs.filter(
            action=EquipmentHistoryLog.Action.ASSIGNED
        ).order_by("-created_at", "-id").first()
        assignment_history.append(
            {
                "employee": assignment.employee,
                "assigned_at": assignment.assigned_at,
                "returned_at": assignment.returned_at,
                "status_snapshot": assigned_log.status_snapshot if assigned_log else "",
                "notes": assignment.remarks,
                "assigned_by": assignment.assigned_by,
            }
        )
    return assignment_history


class InventoryAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.ADMIN)

    def test_func(self):
        return self.request.user.role in self.allowed_roles

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect(_dashboard_url(self.request.user))
        return super().handle_no_permission()


class SuperAdminInventoryAccessMixin(InventoryAccessMixin):
    allowed_roles = (User.Role.SUPER_ADMIN,)


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


class InventorySummaryView(InventoryAccessMixin, TemplateView):
    template_name = "inventory/summary_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_equipment = Equipment.objects.count()
        assigned_equipment = Equipment.objects.filter(current_employee__isnull=False).count()
        status_totals = {code: 0 for code, _label in Equipment.Status.choices}
        for row in Equipment.objects.values("status").annotate(total=Count("id")):
            status_totals[row["status"]] = row["total"]

        context.update(
            {
                "total_equipment": total_equipment,
                "assigned_equipment": assigned_equipment,
                "unassigned_equipment": total_equipment - assigned_equipment,
                "total_supervisors": Supervisor.objects.count(),
                "total_employees": Employee.objects.count(),
                "status_cards": [
                    {"code": code, "label": label, "total": status_totals.get(code, 0)}
                    for code, label in Equipment.Status.choices
                ],
            }
        )
        return context


class EquipmentCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = "inventory/equipment_create.html"

    def form_valid(self, form):
        messages.success(self.request, "Equipment record created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:equipment-create")


class EquipmentAssignmentCreateView(SuperAdminInventoryAccessMixin, FormView):
    form_class = EquipmentAssignmentCreateForm
    template_name = "inventory/equipment_assignment_create.html"

    def form_valid(self, form):
        assignment = self._assign_equipment(
            equipment=form.cleaned_data["equipment"],
            employee=form.cleaned_data["employee"],
            assigned_by=self.request.user,
            assigned_at=form.cleaned_data["assigned_at"],
            notes=form.cleaned_data["notes"],
        )
        messages.success(self.request, "Equipment assigned successfully.")
        return redirect("inventory:equipment-detail", pk=assignment.equipment_id)

    def _assign_equipment(self, equipment, employee, assigned_by, assigned_at, notes):
        assignment = EquipmentAssignment.objects.create(
            equipment=equipment,
            employee=employee,
            assigned_by=assigned_by,
            assigned_at=assigned_at,
            remarks=notes,
        )
        equipment.current_employee = employee
        equipment.last_assigned_at = assigned_at
        equipment.save(update_fields=["current_employee", "last_assigned_at"])

        EquipmentHistoryLog.objects.create(
            equipment=equipment,
            employee=employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.ASSIGNED,
            status_snapshot=equipment.status,
            remarks=notes,
        )
        return assignment


class EquipmentDetailView(SuperAdminInventoryAccessMixin, DetailView):
    model = Equipment
    template_name = "inventory/equipment_detail.html"
    context_object_name = "equipment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        equipment = self.object
        context["active_assignment"] = equipment.assignments.filter(returned_at__isnull=True).select_related(
            "employee", "assigned_by"
        ).first()
        context["assignment_history"] = _build_assignment_history(equipment)
        context["return_form"] = kwargs.get("return_form") or EquipmentReturnForm(prefix="return")
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = EquipmentReturnForm(request.POST, prefix="return")
        if form.is_valid():
            self._return_equipment(
                equipment=self.object,
                returned_at=form.cleaned_data["returned_at"],
                notes=form.cleaned_data["notes"],
            )
            messages.success(request, "Equipment returned successfully.")
            return redirect("inventory:equipment-detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(return_form=form))

    def _return_equipment(self, equipment, returned_at, notes):
        assignment = get_object_or_404(
            EquipmentAssignment.objects.select_related("employee"),
            equipment=equipment,
            returned_at__isnull=True,
        )
        assignment.returned_at = returned_at
        assignment.remarks = notes or assignment.remarks
        assignment.save(update_fields=["returned_at", "remarks"])
        equipment.current_employee = None
        equipment.save(update_fields=["current_employee"])
        EquipmentHistoryLog.objects.create(
            equipment=equipment,
            employee=assignment.employee,
            assignment=assignment,
            action=EquipmentHistoryLog.Action.RETURNED,
            status_snapshot=equipment.status,
            remarks=notes,
        )


class EquipmentHistoryView(SuperAdminInventoryAccessMixin, DetailView):
    model = Equipment
    template_name = "inventory/equipment_history.html"
    context_object_name = "equipment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment_history"] = _build_assignment_history(self.object)
        return context


class SupervisorListView(SuperAdminInventoryAccessMixin, ListView):
    model = Supervisor
    template_name = "inventory/supervisor_list.html"
    context_object_name = "supervisors"

    def get_queryset(self):
        return Supervisor.objects.annotate(member_count=Count("employees")).order_by("full_name", "employee_code")


class SupervisorCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = Supervisor
    form_class = SupervisorForm
    template_name = "inventory/supervisor_create.html"

    def form_valid(self, form):
        messages.success(self.request, "Supervisor created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:supervisor-list")


class EmployeeListView(SuperAdminInventoryAccessMixin, ListView):
    model = Employee
    template_name = "inventory/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        queryset = Employee.objects.select_related("supervisor").order_by("full_name", "employee_code")
        query = self.request.GET.get("q", "").strip()
        supervisor_id = self.request.GET.get("supervisor", "").strip()

        if query:
            queryset = queryset.filter(
                Q(full_name__icontains=query)
                | Q(employee_code__icontains=query)
                | Q(supervisor__full_name__icontains=query)
            )
        if supervisor_id:
            queryset = queryset.filter(supervisor_id=supervisor_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_supervisor"] = self.request.GET.get("supervisor", "").strip()
        context["supervisors"] = Supervisor.objects.order_by("full_name", "employee_code")
        return context


class EmployeeCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "inventory/employee_create.html"

    def form_valid(self, form):
        messages.success(self.request, "Employee created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:employee-list")


class EmployeeAssignSupervisorView(SuperAdminInventoryAccessMixin, FormView):
    form_class = EmployeeAssignSupervisorForm
    template_name = "inventory/employee_assign_supervisor.html"

    def form_valid(self, form):
        employee = form.cleaned_data["employee"]
        supervisor = form.cleaned_data["supervisor"]
        employee.supervisor = supervisor
        employee.save(update_fields=["supervisor"])
        messages.success(self.request, "Employee assigned to supervisor successfully.")
        return redirect("inventory:employee-list")
