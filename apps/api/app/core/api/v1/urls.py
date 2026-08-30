from django.urls import path

from app.core.api.v1.views import HealthAPICheck

urlpatterns = [path("health/", HealthAPICheck.as_view())]
