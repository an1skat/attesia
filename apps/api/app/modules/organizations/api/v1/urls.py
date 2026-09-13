from django.urls import path

from .views import (
    MyOrganizationsView,
    OrganizationDetailView,
    OrganizationLeaveView,
    OrganizationListCreateView,
    OrganizationMemberDetailView,
    OrganizationMembersView,
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
    path(
        "organizations/<int:pk>/members/",
        OrganizationMembersView.as_view(),
        name="organization_members",
    ),
    path(
        "organizations/<int:organization_id>/members/<int:member_id>/",
        OrganizationMemberDetailView.as_view(),
        name="organization_member_detail",
    ),
    path(
        "organizations/<int:organization_id>/leave/",
        OrganizationLeaveView.as_view(),
        name="organization_leave",
    ),
]
