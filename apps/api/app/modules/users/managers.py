from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        ...

    def create_superuser(self, email, password, **extra_fields):
        ...