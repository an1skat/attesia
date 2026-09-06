from django.urls import path

from .views import (
    CustomRefreshToken,
    LoginView,
    RegisterView,
    UserProfileView,
)

app_name = "users"
urlpatterns = [
    path("users/me/", UserProfileView.as_view(), name="user_profile"),
    path("auth/register/", RegisterView.as_view(), name="user_register"),
    path("auth/login/", LoginView.as_view(), name="token_obtain"),
    path("auth/refresh/", CustomRefreshToken.as_view(), name="token_refresh"),
]
