from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

# admin.site.register(User, UserAdmin)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    search_fields = ("email", "display_name")
    readonly_fields = ("last_login", "created_at", "updated_at")

    list_display = (
        "email",
        "display_name",
        "is_staff",
        "is_active",
        "is_superuser",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("display_name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {"fields": ("last_login", "created_at", "updated_at")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "display_name",
                    "usable_password",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
