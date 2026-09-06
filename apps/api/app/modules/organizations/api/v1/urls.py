from django.urls import path

from .views import OrganizationView

app_name = "organizations"

urlpatterns = [path("organizations/", OrganizationView.as_view(), name="organizations")]
