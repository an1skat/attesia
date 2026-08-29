from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

# admin.site.register(User, UserAdmin)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)

    list_display = (
        "email",
        "display_name",
        "is_staff",
        "is_active",
        "is_superuser",
    )
