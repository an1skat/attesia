from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from .models import Organization

User = get_user_model()


def get_user_organizations(*, user: User) -> QuerySet[Organization]:
    return Organization.objects.filter(memberships__user=user).order_by("pk")
