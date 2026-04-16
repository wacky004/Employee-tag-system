from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    EquipmentAssignmentCreateForm,
    EmployeeAssignSupervisorForm,
    EmployeeForm,
    EmployeeSearchForm,
    EquipmentAssignmentForm,
    EquipmentCategoryForm,
    EquipmentForm,
    EquipmentReturnForm,
    SupervisorForm,
)
from .models import (
    Employee,
    Equipment,
    EquipmentAssignment,
    EquipmentCategory,
    EquipmentHistoryLog,
    InventoryAuditLog,
    Supervisor,
)

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


def _create_audit_log(action, actor, target, notes=""):
    InventoryAuditLog.objects.create(
        action=action,
        actor=actor,
        target_type=target._meta.model_name,
        target_id=target.pk,
        notes=notes,
    )


def _filter_equipment_queryset(queryset, params):
    status = params.get("status", "").strip()
    category = params.get("category", "").strip()
    brand = params.get("brand", "").strip()
    supervisor = params.get("supervisor", "").strip()
    assignment = params.get("assignment", "").strip()

    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category_id=category)
    if brand:
        queryset = queryset.filter(brand__icontains=brand)
    if supervisor:
        queryset = queryset.filter(current_employee__supervisor_id=supervisor)
    if assignment == "assigned":
        queryset = queryset.filter(current_employee__isnull=False)
    elif assignment == "unassigned":
        queryset = queryset.filter(current_employee__isnull=True)

    return queryset


def _get_active_assignment(equipment):
    return equipment.assignments.filter(returned_at__isnull=True).select_related("employee", "assigned_by").first()


def _return_equipment_assignment(equipment, returned_at, notes, actor=None):
    assignment = _get_active_assignment(equipment)
    if not assignment:
        return None

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
    _create_audit_log(
        InventoryAuditLog.Action.EQUIPMENT_RETURNED,
        actor,
        equipment,
        notes=notes or f"Returned from employee {assignment.employee.full_name}.",
    )
    return assignment


def _return_all_employee_equipment(employee, returned_at, actor=None):
    returned_count = 0
    notes = f"Automatically returned because {employee.full_name} was marked inactive."
    assigned_equipment = Equipment.objects.filter(current_employee=employee).order_by("asset_code", "name")

    for equipment in assigned_equipment:
        assignment = _return_equipment_assignment(
            equipment=equipment,
            returned_at=returned_at,
            notes=notes,
            actor=actor,
        )
        if assignment:
            returned_count += 1

    return returned_count


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
                instance = form.save()
                audit_action_map = {
                    "create_supervisor": InventoryAuditLog.Action.SUPERVISOR_CREATED,
                    "create_employee": InventoryAuditLog.Action.EMPLOYEE_CREATED,
                    "create_equipment": InventoryAuditLog.Action.EQUIPMENT_CREATED,
                }
                audit_action = audit_action_map.get(action)
                if audit_action:
                    _create_audit_log(audit_action, request.user, instance)
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
        total_equipment = equipment_list.count()
        total_assigned = equipment_list.filter(current_employee__isnull=False).count()
        total_available = equipment_list.filter(current_employee__isnull=True).count()
        recent_activity = list(
            InventoryAuditLog.objects.select_related("actor").order_by("-timestamp", "-id")[:8]
        )

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
                "total_equipment": total_equipment,
                "total_assigned": total_assigned,
                "total_available": total_available,
                "total_defective": summary_counts.get(Equipment.Status.DEFECTIVE, 0),
                "total_employees": Employee.objects.count(),
                "recent_activity": recent_activity,
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
            _create_audit_log(
                InventoryAuditLog.Action.EQUIPMENT_RETURNED,
                assigned_by,
                equipment,
                notes="Automatically closed before reassignment.",
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
        _create_audit_log(
            InventoryAuditLog.Action.EQUIPMENT_ASSIGNED,
            assigned_by,
            equipment,
            notes=remarks or f"Assigned to {employee.full_name}.",
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


class AuditLogListView(SuperAdminInventoryAccessMixin, ListView):
    model = InventoryAuditLog
    template_name = "inventory/audit_log_list.html"
    context_object_name = "audit_logs"
    paginate_by = 50

    def get_queryset(self):
        return InventoryAuditLog.objects.select_related("actor").order_by("-timestamp", "-id")


class EquipmentReportListView(InventoryAccessMixin, ListView):
    model = Equipment
    template_name = "inventory/equipment_report_list.html"
    context_object_name = "equipment_list"

    report_title = "Equipment Report"
    report_description = "Browse equipment with filter options."

    def get_queryset(self):
        queryset = Equipment.objects.select_related(
            "category",
            "current_employee",
            "current_employee__supervisor",
        ).order_by("asset_code", "name")
        return _filter_equipment_queryset(queryset, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "report_title": self.report_title,
                "report_description": self.report_description,
                "status_choices": Equipment.Status.choices,
                "categories": EquipmentCategory.objects.order_by("name"),
                "supervisors": Supervisor.objects.order_by("full_name", "employee_code"),
                "selected_status": self.request.GET.get("status", "").strip(),
                "selected_category": self.request.GET.get("category", "").strip(),
                "brand_query": self.request.GET.get("brand", "").strip(),
                "selected_supervisor": self.request.GET.get("supervisor", "").strip(),
                "selected_assignment": self.request.GET.get("assignment", "").strip(),
            }
        )
        return context


class DefectiveEquipmentReportView(EquipmentReportListView):
    report_title = "Defective Equipment"
    report_description = "All equipment currently marked as defective."

    def get_queryset(self):
        queryset = Equipment.objects.select_related(
            "category",
            "current_employee",
            "current_employee__supervisor",
        ).filter(status=Equipment.Status.DEFECTIVE).order_by("asset_code", "name")
        return queryset


class UnusedEquipmentReportView(EquipmentReportListView):
    report_title = "Unused Equipment"
    report_description = "All equipment currently marked as unused."

    def get_queryset(self):
        queryset = Equipment.objects.select_related(
            "category",
            "current_employee",
            "current_employee__supervisor",
        ).filter(status=Equipment.Status.UNUSED).order_by("asset_code", "name")
        return queryset


class AssignedEquipmentReportView(EquipmentReportListView):
    report_title = "Assigned Equipment"
    report_description = "All equipment currently assigned to employees."

    def get_queryset(self):
        queryset = Equipment.objects.select_related(
            "category",
            "current_employee",
            "current_employee__supervisor",
        ).filter(current_employee__isnull=False).order_by("asset_code", "name")
        return queryset


class UnassignedEquipmentReportView(EquipmentReportListView):
    report_title = "Unassigned Equipment"
    report_description = "All equipment currently available for assignment."

    def get_queryset(self):
        queryset = Equipment.objects.select_related(
            "category",
            "current_employee",
            "current_employee__supervisor",
        ).filter(current_employee__isnull=True).order_by("asset_code", "name")
        return queryset


class EquipmentCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = "inventory/equipment_create.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        _create_audit_log(InventoryAuditLog.Action.EQUIPMENT_CREATED, self.request.user, self.object)
        messages.success(self.request, "Equipment record created successfully.")
        return response

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
        _create_audit_log(
            InventoryAuditLog.Action.EQUIPMENT_ASSIGNED,
            assigned_by,
            equipment,
            notes=notes or f"Assigned to {employee.full_name}.",
        )
        return assignment


class EquipmentDetailView(SuperAdminInventoryAccessMixin, DetailView):
    model = Equipment
    template_name = "inventory/equipment_detail.html"
    context_object_name = "equipment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        equipment = self.object
        context["active_assignment"] = _get_active_assignment(equipment)
        context["assignment_history"] = _build_assignment_history(equipment)
        context["return_form"] = kwargs.get("return_form") or EquipmentReturnForm(prefix="return")
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = EquipmentReturnForm(request.POST, prefix="return")
        if form.is_valid():
            assignment = _return_equipment_assignment(
                equipment=self.object,
                returned_at=form.cleaned_data["returned_at"],
                notes=form.cleaned_data["notes"],
                actor=request.user,
            )
            if not assignment:
                messages.error(request, "This equipment has already been returned.")
                return redirect("inventory:equipment-detail", pk=self.object.pk)
            messages.success(request, "Equipment returned successfully.")
            return redirect("inventory:equipment-detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(return_form=form))


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
        response = super().form_valid(form)
        _create_audit_log(InventoryAuditLog.Action.SUPERVISOR_CREATED, self.request.user, self.object)
        messages.success(self.request, "Supervisor created successfully.")
        return response

    def get_success_url(self):
        return reverse("inventory:supervisor-list")


class EquipmentCategoryListView(SuperAdminInventoryAccessMixin, ListView):
    model = EquipmentCategory
    template_name = "inventory/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return EquipmentCategory.objects.order_by("name", "code")


class EquipmentCategoryCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = EquipmentCategory
    form_class = EquipmentCategoryForm
    template_name = "inventory/category_create.html"

    def form_valid(self, form):
        messages.success(self.request, "Equipment category created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory:category-list")


class SupervisorUpdateView(SuperAdminInventoryAccessMixin, UpdateView):
    model = Supervisor
    form_class = SupervisorForm
    template_name = "inventory/supervisor_update.html"

    def form_valid(self, form):
        messages.success(self.request, "Supervisor updated successfully.")
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


class EmployeeSearchView(SuperAdminInventoryAccessMixin, ListView):
    model = Employee
    template_name = "inventory/employee_search.html"
    context_object_name = "employees"

    def get_queryset(self):
        queryset = Employee.objects.select_related("supervisor").prefetch_related("current_equipment").order_by(
            "full_name", "employee_code"
        )
        self.form = EmployeeSearchForm(self.request.GET or None)
        if self.form.is_valid():
            query = self.form.cleaned_data.get("q", "").strip()
            if query:
                queryset = queryset.filter(
                    Q(full_name__icontains=query)
                    | Q(employee_code__icontains=query)
                    | Q(supervisor__full_name__icontains=query)
                )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = getattr(self, "form", EmployeeSearchForm())
        return context


class EmployeeDetailView(SuperAdminInventoryAccessMixin, DetailView):
    model = Employee
    template_name = "inventory/employee_detail.html"
    context_object_name = "employee"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        current_equipment = list(
            Equipment.objects.filter(current_employee=employee).order_by("asset_code", "name")
        )
        context["assignment_history"] = EquipmentAssignment.objects.select_related(
            "equipment", "assigned_by"
        ).filter(employee=employee).order_by("-assigned_at", "-id")
        context["current_equipment"] = current_equipment
        context["current_equipment_rows"] = kwargs.get("current_equipment_rows") or [
            {
                "equipment": equipment,
                "return_form": EquipmentReturnForm(prefix=f"return-{equipment.id}"),
            }
            for equipment in current_equipment
        ]
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        equipment = get_object_or_404(
            Equipment.objects.select_related("current_employee"),
            pk=request.POST.get("equipment_id"),
            current_employee=self.object,
        )
        form = EquipmentReturnForm(request.POST, prefix=f"return-{equipment.id}")
        if form.is_valid():
            assignment = _return_equipment_assignment(
                equipment=equipment,
                returned_at=form.cleaned_data["returned_at"],
                notes=form.cleaned_data["notes"],
                actor=request.user,
            )
            if not assignment:
                messages.error(request, "This equipment has already been returned.")
                return redirect("inventory:employee-detail", pk=self.object.pk)
            messages.success(request, "Equipment returned successfully.")
            return redirect("inventory:employee-detail", pk=self.object.pk)

        current_equipment = list(
            Equipment.objects.filter(current_employee=self.object).order_by("asset_code", "name")
        )
        current_equipment_rows = []
        for item in current_equipment:
            current_equipment_rows.append(
                {
                    "equipment": item,
                    "return_form": form if item.id == equipment.id else EquipmentReturnForm(prefix=f"return-{item.id}"),
                }
            )
        return self.render_to_response(self.get_context_data(current_equipment_rows=current_equipment_rows))


class EmployeeCreateView(SuperAdminInventoryAccessMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "inventory/employee_create.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        _create_audit_log(InventoryAuditLog.Action.EMPLOYEE_CREATED, self.request.user, self.object)
        messages.success(self.request, "Employee created successfully.")
        return response

    def get_success_url(self):
        return reverse("inventory:employee-list")


class EmployeeUpdateView(SuperAdminInventoryAccessMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "inventory/employee_update.html"

    def form_valid(self, form):
        original = self.get_object()
        became_inactive = original.is_active and not form.cleaned_data["is_active"]
        messages.success(self.request, "Employee updated successfully.")
        response = super().form_valid(form)
        if became_inactive:
            returned_count = _return_all_employee_equipment(
                employee=self.object,
                returned_at=timezone.now(),
                actor=self.request.user,
            )
            if returned_count:
                messages.info(
                    self.request,
                    f"{returned_count} equipment item(s) were automatically returned to inventory.",
                )
        return response

    def get_success_url(self):
        return reverse("inventory:employee-detail", kwargs={"pk": self.object.pk})


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


class EquipmentUpdateView(SuperAdminInventoryAccessMixin, UpdateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = "inventory/equipment_update.html"

    def form_valid(self, form):
        original = self.get_object()
        old_status = original.status
        response = super().form_valid(form)
        notes = "Equipment details updated."
        if old_status != self.object.status:
            notes = f"Status updated from {old_status} to {self.object.status}."
        _create_audit_log(InventoryAuditLog.Action.EQUIPMENT_UPDATED, self.request.user, self.object, notes=notes)
        messages.success(self.request, "Equipment updated successfully.")
        return response

    def get_success_url(self):
        return reverse("inventory:equipment-detail", kwargs={"pk": self.object.pk})
