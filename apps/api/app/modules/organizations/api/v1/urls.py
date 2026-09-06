from django.urls import path

from .views import (
    MyOrganizationsView,
    OrganizationDetailView,
    OrganizationListCreateView,
)

app_name = "organizations"

urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organizations"),
    path(
        "organizations/<int:pk>/",
        OrganizationDetailView.as_view(),
        name="organization_detail",
    ),
    path("me/organizations/", MyOrganizationsView.as_view(), name="my_organizations"),
]
