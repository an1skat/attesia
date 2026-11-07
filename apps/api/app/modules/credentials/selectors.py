from django.db.models import Prefetch, QuerySet

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.events.models import Event
from app.modules.organizations.models import OrganizationMembership


def _credentials_with_snapshots() -> QuerySet[Credential]:
    return (
        Credential.objects.select_related("finalization")
        # Only the finalization summary is exposed; skip loading the payload JSON.
        .defer("finalization__payload")
        .prefetch_related(
            Prefetch(
                "achievement_snapshots",
                queryset=CredentialAchievement.objects.order_by("id"),
            )
        )
    )


def get_credentials_for_event(
    *,
    event: Event,
    participant_id: int | None = None,
) -> QuerySet[Credential]:
    queryset = _credentials_with_snapshots().filter(event=event)
    if participant_id is not None:
        queryset = queryset.filter(participant_id=participant_id)
    return queryset.order_by("-issued_at", "-id")


def get_credential_by_public_id(*, public_id, user) -> Credential:
    """Return a credential readable by ``user`` within its issuer organization.

    Credentials without an attached organization, or issued by organizations the
    user is not a member of, raise ``Credential.DoesNotExist`` so their existence
    is not disclosed.
    """
    return (
        _credentials_with_snapshots()
        .filter(
            organization__memberships__user=user,
            organization__memberships__role__in=OrganizationMembership.Role.values,
        )
        .get(public_id=public_id)
    )
