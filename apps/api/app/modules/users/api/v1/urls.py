from django.urls import path

from .views import RegisterView

app_name = "users"
urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
]
