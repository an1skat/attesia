from django.db import transaction
from rest_framework.exceptions import ValidationError

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.events.finalization import (
    build_finalization_payload,
    hash_finalization_payload,
)
from app.modules.events.models import (
    Event,
    EventParticipant,
    EventStatus,
    ParticipantAchievement,
)
from app.modules.organizations.models import Organization, OrganizationMembership


class CredentialService:
    @staticmethod
    @transaction.atomic
    def issue_credential(
        *, participant: EventParticipant, participant_achievements, issued_by
    ) -> Credential:
        event = Event.objects.select_for_update().get(pk=participant.event_id)
        participant = EventParticipant.objects.get(pk=participant.pk, event=event)
        if event.status != EventStatus.FINISHED:
            raise ValidationError({"detail": "Credentials require a finished event."})
        finalization = event.finalizations.filter(version=1).first()
        if finalization is None:
            raise ValidationError({"detail": "The event has no finalization."})
        if (
            finalization.schema_version != 1
            or finalization.payload.get("schema_version") != finalization.schema_version
            or hash_finalization_payload(finalization.payload)
            != finalization.payload_hash
            or hash_finalization_payload(build_finalization_payload(event))
            != finalization.payload_hash
        ):
            raise ValidationError(
                {
                    "detail": "The event results no longer match the finalization commitment."
                }
            )
        if event.organization_id is None:
            raise ValidationError(
                {"detail": "The event must have an issuer organization."}
            )
        organization = Organization.objects.select_for_update().get(
            pk=event.organization_id
        )
        if not OrganizationMembership.objects.filter(
            organization=organization,
            user=issued_by,
            role__in=[
                OrganizationMembership.Role.OWNER,
                OrganizationMembership.Role.ADMIN,
            ],
        ).exists():
            raise ValidationError(
                {"detail": "Only an organization owner or admin can issue credentials."}
            )
        ids = [result.pk for result in participant_achievements]
        if not ids or None in ids or len(ids) != len(set(ids)):
            raise ValidationError(
                {
                    "participant_achievements": "Select at least one achievement without duplicates."
                }
            )
        results = list(
            ParticipantAchievement.objects.filter(
                pk__in=ids,
                participant=participant,
                achievement__event=event,
            )
            .select_related("achievement")
            .order_by("id")
        )
        finalized_ids = {
            result["id"] for result in finalization.payload["participant_achievements"]
        }
        if len(results) != len(ids) or not set(ids).issubset(finalized_ids):
            raise ValidationError(
                {
                    "participant_achievements": "All achievements must belong to this participant, event, and finalization."
                }
            )
        credential = Credential.objects.create(
            organization=organization,
            organization_title=organization.name,
            event=event,
            event_title=event.title,
            participant=participant,
            recipient_user=participant.user,
            recipient_name=participant.name,
            finalization=finalization,
            issued_by=issued_by,
        )
        CredentialAchievement.objects.bulk_create(
            [
                CredentialAchievement(
                    credential=credential,
                    participant_achievement=result,
                    title=result.achievement.title,
                    description=result.achievement.description,
                    kind=result.achievement.kind,
                    rank=result.achievement.rank,
                )
                for result in results
            ]
        )
        return credential
