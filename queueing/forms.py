from django import forms

from accounts.models import Company

from .models import QueueCounter, QueueDisplayScreen, QueueService, QueueSystemSetting, QueueTicket


class QueueCompanyAwareFormMixin:
    company_field_name = "company"

    def __init__(self, *args, company=None, can_manage_companies=False, **kwargs):
        self.current_company = company
        self.can_manage_companies = can_manage_companies
        super().__init__(*args, **kwargs)
        if self.company_field_name in self.fields:
            company_field = self.fields[self.company_field_name]
            if self.can_manage_companies:
                company_field.queryset = Company.objects.order_by("name")
            elif self.current_company:
                company_field.queryset = Company.objects.filter(pk=self.current_company.pk)
                company_field.initial = self.current_company
            else:
                company_field.queryset = Company.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        if not self.can_manage_companies and self.current_company and self.company_field_name in self.fields:
            cleaned_data[self.company_field_name] = self.current_company
        return cleaned_data


class QueueServiceForm(QueueCompanyAwareFormMixin, forms.ModelForm):
    class Meta:
        model = QueueService
        fields = [
            "company",
            "name",
            "code",
            "description",
            "is_active",
            "max_queue_limit",
            "current_queue_number",
            "allow_priority",
            "show_in_ticket_generation",
        ]

    def __init__(self, *args, company=None, can_manage_companies=False, **kwargs):
        super().__init__(*args, company=company, can_manage_companies=can_manage_companies, **kwargs)
        if not self.instance.pk and self.current_company:
            default_setting = QueueSystemSetting.objects.filter(company=self.current_company).first()
            if default_setting:
                self.fields["max_queue_limit"].initial = default_setting.default_max_queue_per_service

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company") or self.current_company
        code = cleaned_data.get("code")
        max_queue_limit = cleaned_data.get("max_queue_limit")
        current_queue_number = cleaned_data.get("current_queue_number")
        if company and code:
            queryset = QueueService.objects.filter(company=company, code=code)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                self.add_error("code", "A queue service with this code already exists for this tenant.")
        if max_queue_limit is not None and current_queue_number is not None and current_queue_number > max_queue_limit:
            self.add_error("current_queue_number", "Current queue number cannot be greater than the max queue limit.")
        return cleaned_data


class QueueCounterForm(QueueCompanyAwareFormMixin, forms.ModelForm):
    class Meta:
        model = QueueCounter
        fields = [
            "company",
            "name",
            "assigned_service",
            "is_active",
        ]

    def __init__(self, *args, company=None, can_manage_companies=False, **kwargs):
        super().__init__(*args, company=company, can_manage_companies=can_manage_companies, **kwargs)
        service_queryset = QueueService.objects.filter(is_active=True).order_by("name", "code")
        if self.can_manage_companies:
            selected_company = self.data.get("company") or getattr(self.instance, "company_id", None)
            if selected_company:
                service_queryset = service_queryset.filter(company_id=selected_company)
        elif self.current_company:
            service_queryset = service_queryset.filter(company=self.current_company)
        else:
            service_queryset = QueueService.objects.none()
        self.fields["assigned_service"].queryset = service_queryset


class QueueDisplayScreenForm(QueueCompanyAwareFormMixin, forms.ModelForm):
    class Meta:
        model = QueueDisplayScreen
        fields = [
            "company",
            "name",
            "slug",
            "services",
            "refresh_interval_seconds",
            "is_active",
        ]

    def __init__(self, *args, company=None, can_manage_companies=False, **kwargs):
        super().__init__(*args, company=company, can_manage_companies=can_manage_companies, **kwargs)
        service_queryset = QueueService.objects.filter(is_active=True).order_by("name", "code")
        if self.can_manage_companies:
            selected_company = self.data.get("company") or getattr(self.instance, "company_id", None)
            if selected_company:
                service_queryset = service_queryset.filter(company_id=selected_company)
        elif self.current_company:
            service_queryset = service_queryset.filter(company=self.current_company)
        else:
            service_queryset = QueueService.objects.none()
        self.fields["services"].queryset = service_queryset

    def clean_slug(self):
        return (self.cleaned_data.get("slug") or "").strip().lower()


class QueueTicketGenerationForm(forms.ModelForm):
    class Meta:
        model = QueueTicket
        fields = ["service", "is_priority"]

    def __init__(self, *args, company=None, **kwargs):
        self.current_company = company
        super().__init__(*args, **kwargs)
        service_queryset = QueueService.objects.filter(
            is_active=True,
            show_in_ticket_generation=True,
        ).order_by("name", "code")
        if self.current_company:
            service_queryset = service_queryset.filter(company=self.current_company)
        self.fields["service"].queryset = service_queryset

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        if not service:
            return cleaned_data
        if not service.is_active or not service.show_in_ticket_generation:
            raise forms.ValidationError("This service is not available for ticket generation.")
        if service.current_queue_number >= service.max_queue_limit:
            raise forms.ValidationError("Maximum queue limit reached for this service")
        return cleaned_data


class QueueCallNextForm(forms.Form):
    service = forms.ModelChoiceField(queryset=QueueService.objects.none())
    counter = forms.ModelChoiceField(queryset=QueueCounter.objects.none(), required=False)

    def __init__(self, *args, company=None, **kwargs):
        self.current_company = company
        super().__init__(*args, **kwargs)
        service_queryset = QueueService.objects.filter(is_active=True).order_by("name", "code")
        counter_queryset = QueueCounter.objects.filter(is_active=True).order_by("name")
        if self.current_company:
            service_queryset = service_queryset.filter(company=self.current_company)
            counter_queryset = counter_queryset.filter(company=self.current_company)
        self.fields["service"].queryset = service_queryset
        self.fields["counter"].queryset = counter_queryset


class QueueTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = QueueTicket
        fields = [
            "service",
            "status",
            "assigned_counter",
            "is_priority",
        ]

    def __init__(self, *args, company=None, **kwargs):
        self.current_company = company
        super().__init__(*args, **kwargs)
        service_queryset = QueueService.objects.order_by("name", "code")
        counter_queryset = QueueCounter.objects.order_by("name")
        if self.current_company:
            service_queryset = service_queryset.filter(company=self.current_company)
            counter_queryset = counter_queryset.filter(company=self.current_company)
        self.fields["service"].queryset = service_queryset
        self.fields["assigned_counter"].queryset = counter_queryset
