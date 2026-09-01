from django.urls import path

from .views import HealthAPICheck

app_name = "v1"
urlpatterns = [path("health/", HealthAPICheck.as_view(), name="health-check")]
