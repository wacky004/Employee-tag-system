from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import Company

User = get_user_model()


class OrganizationLoginForm(AuthenticationForm):
    field_order = ["organization", "username", "password"]
    organization = forms.CharField(
        label="Organization (required for tenant users only)",
        max_length=150,
        required=False,
        help_text="Enter your company code or company name if your account belongs to a tenant. Platform superadmins can leave this blank.",
    )

    def clean(self):
        organization = self.cleaned_data.get("organization", "").strip()
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
            if self.user_cache.company_id:
                if not organization:
                    raise forms.ValidationError(
                        "Please enter your organization name or code.",
                        code="organization_required",
                    )
                if not self.user_cache.matches_organization(organization):
                    raise forms.ValidationError(
                        "The organization does not match this account. Please check the company name or code.",
                        code="invalid_organization",
                    )
            elif not self.user_cache.is_platform_super_admin() and organization and not self.user_cache.matches_organization(organization):
                raise forms.ValidationError(
                    "The organization does not match this account. Please check the company name or code.",
                    code="invalid_organization",
                )

        return self.cleaned_data


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "code",
            "is_active",
            "can_use_tagging",
            "can_use_inventory",
            "can_use_queueing",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].help_text = "Use a short company code for organization login, such as ACME or NORTHSTAR."
