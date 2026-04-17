from django import forms

from accounts.models import Company

from .models import QueueCounter, QueueDisplayScreen, QueueService


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
        ]


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
            "services",
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
