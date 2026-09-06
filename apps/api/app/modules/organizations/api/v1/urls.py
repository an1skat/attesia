from django.urls import path

from .views import OrganizationCreateView

app_name = "organizations"

urlpatterns = [
    path("organizations/", OrganizationCreateView.as_view(), name="organization_create")
]
