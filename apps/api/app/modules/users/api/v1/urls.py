from django.urls import path

from .views import CustomRefreshToken, LoginView, RegisterView

app_name = "users"
urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="token_obtain"),
    path("auth/refresh/", CustomRefreshToken.as_view(), name="token_refresh"),
]
