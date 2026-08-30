from django.urls import path

from app.core.api.v1.views import HealthAPICheck

app_name = "v1"
urlpatterns = [path("health/", HealthAPICheck.as_view())]
