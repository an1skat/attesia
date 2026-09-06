from django.urls import path

from .views import MyOrganizationsView, OrganizationCreateView

app_name = "organizations"

urlpatterns = [
    path("organizations/", OrganizationCreateView.as_view(), name="organizations"),
    path("me/organizations/", MyOrganizationsView.as_view(), name="my_organizations"),
]
