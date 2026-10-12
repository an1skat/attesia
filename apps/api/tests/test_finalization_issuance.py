import hashlib
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.credentials.services import CredentialService
from app.modules.events.finalization import (
    build_finalization_payload,
    hash_finalization_payload,
)
from app.modules.events.models import (
    Event,
    EventAchievement,
    EventFinalization,
    EventParticipant,
    EventStatus,
    ParticipantAchievement,
)
from app.modules.events.services import EventService
from app.modules.organizations.models import Organization, OrganizationMembership


class FinalizationIssuanceTests(APITestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            email="owner@example.com", display_name="Owner"
        )
        self.organization = Organization.objects.create(name="Organizer")
        self.membership = OrganizationMembership.objects.create(
            organization=self.organization, user=self.actor, role="owner"
        )
        self.event = Event.objects.create(
            title="Змагання",
            organization=self.organization,
            status=EventStatus.IN_PROGRESS,
        )
        self.participant = EventParticipant.objects.create(
            event=self.event, name="Recipient", email="recipient@example.com"
        )
        self.achievement = EventAchievement.objects.create(
            event=self.event,
            title="Winner",
            kind="place",
            rank=1,
            description="First place",
        )
        self.result = ParticipantAchievement.objects.create(
            participant=self.participant, achievement=self.achievement
        )

    def finalize(self):
        return EventService.finalize_event(event=self.event, finalized_by=self.actor)

    def issue(self, results=None):
        return CredentialService.issue_credential(
            participant=self.participant,
            participant_achievements=[self.result] if results is None else results,
            issued_by=self.actor,
        )

    def test_finalization_payload_and_hash(self):
        finalization = self.finalize()
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.FINISHED)
        self.assertEqual((finalization.version, finalization.schema_version), (1, 1))
        payload = finalization.payload
        self.assertEqual(payload, build_finalization_payload(self.event))
        self.assertEqual(payload["event"]["organization_id"], self.organization.pk)
        self.assertEqual(payload["participants"][0]["id"], self.participant.pk)
        self.assertEqual(payload["event_achievements"][0]["rank"], 1)
        self.assertEqual(payload["participant_achievements"][0]["id"], self.result.pk)
        self.assertEqual(payload["schema_version"], finalization.schema_version)
        self.assertEqual(set(payload["participants"][0]), {"id", "name"})
        self.assertEqual(
            set(payload["participant_achievements"][0]),
            {"id", "participant_id", "achievement_id"},
        )
        expected = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        self.assertEqual(finalization.payload_hash, expected)
        self.assertEqual(
            hash_finalization_payload(dict(reversed(list(payload.items())))), expected
        )
        self.assertEqual(finalization.finalized_by, self.actor)

    def test_collections_use_id_order(self):
        second = EventAchievement.objects.create(
            event=self.event, title="Earlier alphabetically", kind="finalist"
        )
        other = EventParticipant.objects.create(
            event=self.event, name="Another", email="another@example.com"
        )
        awarded = ParticipantAchievement.objects.create(
            participant=other, achievement=second
        )
        payload = self.finalize().payload
        self.assertEqual(
            [x["id"] for x in payload["participants"]], [self.participant.pk, other.pk]
        )
        self.assertEqual(
            [x["id"] for x in payload["event_achievements"]],
            [self.achievement.pk, second.pk],
        )
        self.assertEqual(
            [x["id"] for x in payload["participant_achievements"]],
            [self.result.pk, awarded.pk],
        )

    def test_finalization_atomic(self):
        with (
            patch.object(
                EventFinalization.objects,
                "create",
                side_effect=RuntimeError("storage failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.finalize()
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.IN_PROGRESS)
        self.assertFalse(EventFinalization.objects.exists())

    def test_duplicate_and_invalid_transitions_rejected(self):
        for state in [
            EventStatus.PLANNED,
            EventStatus.REGISTRATION_OPEN,
            EventStatus.CANCELED,
            EventStatus.FINISHED,
        ]:
            Event.objects.filter(pk=self.event.pk).update(status=state)
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self.finalize()
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.IN_PROGRESS)
        self.finalize()
        with self.assertRaises(ValidationError):
            self.finalize()
        self.assertEqual(EventFinalization.objects.count(), 1)

    def test_api_finalize_permissions(self):
        url = reverse("events:event_finalize", kwargs={"pk": self.event.pk})
        self.assertEqual(self.client.post(url).status_code, 401)
        self.client.force_authenticate(self.actor)
        self.membership.role = "member"
        self.membership.save()
        self.assertEqual(self.client.post(url).status_code, 403)
        self.membership.role = "admin"
        self.membership.save()
        self.assertEqual(self.client.post(url).status_code, 201)
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_normal_finished_status_bypass_rejected(self):
        self.client.force_authenticate(self.actor)
        url = reverse("events:event_detail", kwargs={"pk": self.event.pk})
        self.assertEqual(
            self.client.patch(url, {"status": "finished"}).status_code, 400
        )
        url = reverse(
            "events:organization_event_list_create",
            kwargs={"organization_id": self.organization.pk},
        )
        self.assertEqual(
            self.client.post(
                url, {"title": "Bypass", "status": "finished"}
            ).status_code,
            400,
        )
        self.assertFalse(EventFinalization.objects.exists())

    def test_sealed_api_writes_and_reads(self):
        self.finalize()
        self.client.force_authenticate(self.actor)
        cases = [
            ("patch", "event_detail", {"pk": self.event.pk}, {"title": "Changed"}),
            ("patch", "event_detail", {"pk": self.event.pk}, {"status": "in_progress"}),
            (
                "post",
                "event_participant_list",
                {"event_id": self.event.pk},
                {"name": "New", "email": "new@example.com"},
            ),
            (
                "delete",
                "event_participant_detail",
                {"event_id": self.event.pk, "participant_id": self.participant.pk},
                {},
            ),
            (
                "post",
                "event_achievement_list",
                {"event_id": self.event.pk},
                {"title": "New", "kind": "other"},
            ),
            (
                "delete",
                "event_achievement_detail",
                {"event_id": self.event.pk, "achievement_id": self.achievement.pk},
                {},
            ),
            (
                "post",
                "participant_achievement_list",
                {"event_id": self.event.pk},
                {
                    "participant": self.participant.pk,
                    "achievement": self.achievement.pk,
                },
            ),
            (
                "delete",
                "participant_achievement_detail",
                {"event_id": self.event.pk, "pk": self.result.pk},
                {},
            ),
        ]
        for method, name, kwargs, data in cases:
            with self.subTest(name=name, method=method):
                self.assertEqual(
                    getattr(self.client, method)(
                        reverse("events:" + name, kwargs=kwargs), data
                    ).status_code,
                    400,
                )
        self.membership.role = "member"
        self.membership.save()
        for name in [
            "event_participant_list",
            "participant_achievement_list",
            "event_achievement_list",
        ]:
            self.assertEqual(
                self.client.get(
                    reverse("events:" + name, kwargs={"event_id": self.event.pk})
                ).status_code,
                200,
            )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(
                reverse("events:event_detail", kwargs={"pk": self.event.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "events:event_achievement_list", kwargs={"event_id": self.event.pk}
                )
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "events:event_participant_list", kwargs={"event_id": self.event.pk}
                )
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "events:participant_achievement_list",
                    kwargs={"event_id": self.event.pk},
                )
            ).status_code,
            401,
        )

    def test_stale_event_cannot_bypass_seal(self):
        self.finalize()
        with self.assertRaises(ValidationError):
            EventService.update_event(
                event=self.event, validated_data={"title": "Stale"}
            )
        with self.assertRaises(ValidationError):
            EventService.add_participant(
                event=self.event,
                validated_data={"name": "New", "email": "new@example.com"},
            )

    def test_historical_deletion_protection_and_unique_version(self):
        finalization = self.finalize()
        with self.assertRaises(ProtectedError):
            self.event.delete()
        self.issue()
        with self.assertRaises(ProtectedError):
            finalization.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventFinalization.objects.create(
                event=self.event,
                version=1,
                payload={},
                payload_hash="0" * 64,
                finalized_by=self.actor,
            )

    def test_issuance_snapshots_and_multiple_credentials(self):
        second = EventAchievement.objects.create(
            event=self.event, title="Finalist", kind="finalist"
        )
        result = ParticipantAchievement.objects.create(
            participant=self.participant, achievement=second
        )
        finalization = self.finalize()
        self.organization.name = "Issuer renamed"
        self.organization.save()
        for role in ["owner", "admin"]:
            self.membership.role = role
            self.membership.save()
            credential = self.issue([self.result, result])
            self.assertEqual(credential.achievement_snapshots.count(), 2)
            self.assertEqual(credential.organization_title, "Issuer renamed")
            self.assertEqual(credential.event_title, self.event.title)
            self.assertEqual(credential.recipient_name, "Recipient")
            self.assertIsNone(credential.recipient_user)
            self.assertEqual(credential.participant, self.participant)
            self.assertEqual(credential.finalization, finalization)
            self.assertEqual(credential.organization, self.organization)
            self.assertEqual(credential.issued_by, self.actor)
            snapshot = credential.achievement_snapshots.get(
                participant_achievement=self.result
            )
            self.assertEqual(
                (snapshot.title, snapshot.description, snapshot.kind, snapshot.rank),
                ("Winner", "First place", "place", 1),
            )
        self.assertEqual(Credential.objects.count(), 2)

    def test_single_achievement_and_recipient_user(self):
        self.participant.user = self.actor
        self.participant.save()
        self.finalize()
        credential = self.issue()
        self.assertEqual(credential.recipient_user, self.actor)
        self.assertEqual(credential.recipient_name, self.participant.name)
        self.assertEqual(credential.achievement_snapshots.count(), 1)

    def test_source_deletions_preserve_snapshots(self):
        self.finalize()
        credential = self.issue()
        snapshot = credential.achievement_snapshots.get()
        self.result.delete()
        snapshot.refresh_from_db()
        self.assertIsNone(snapshot.participant_achievement)
        self.assertEqual(
            (snapshot.title, snapshot.description, snapshot.kind, snapshot.rank),
            ("Winner", "First place", "place", 1),
        )
        self.participant.delete()
        credential.refresh_from_db()
        self.assertIsNone(credential.participant)
        self.assertEqual(
            (
                credential.recipient_name,
                credential.event_title,
                credential.organization_title,
            ),
            ("Recipient", "Змагання", "Organizer"),
        )

    def test_snapshot_unique_source_within_credential(self):
        self.finalize()
        credential = self.issue()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CredentialAchievement.objects.create(
                credential=credential,
                participant_achievement=self.result,
                title="Duplicate",
            )

    def test_issuance_preconditions(self):
        with self.assertRaises(ValidationError):
            self.issue()
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.FINISHED)
        with self.assertRaises(ValidationError):
            self.issue()
        Event.objects.filter(pk=self.event.pk).update(status=EventStatus.IN_PROGRESS)
        self.finalize()
        for results in [[], [self.result, self.result]]:
            with self.subTest(results=results), self.assertRaises(ValidationError):
                self.issue(results)
        self.membership.role = "member"
        self.membership.save()
        with self.assertRaises(ValidationError):
            self.issue()
        self.assertFalse(Credential.objects.exists())

    def test_cross_participant_and_event_rejected(self):
        other = EventParticipant.objects.create(
            event=self.event, name="Other", email="other@example.com"
        )
        other_result = ParticipantAchievement.objects.create(
            participant=other, achievement=self.achievement
        )
        other_event = Event.objects.create(
            title="Other", organization=self.organization, status="in_progress"
        )
        foreign_participant = EventParticipant.objects.create(
            event=other_event, name="Foreign", email="foreign@example.com"
        )
        foreign_achievement = EventAchievement.objects.create(
            event=other_event, title="Foreign"
        )
        foreign_result = ParticipantAchievement.objects.create(
            participant=foreign_participant, achievement=foreign_achievement
        )
        self.finalize()
        for result in [other_result, foreign_result]:
            with self.subTest(result=result.pk), self.assertRaises(ValidationError):
                self.issue([result])

    def test_commitment_detects_tampering(self):
        finalization = self.finalize()
        for model, pk, field, value in [
            (Event, self.event.pk, "title", "Tampered"),
            (EventParticipant, self.participant.pk, "name", "Tampered"),
            (EventAchievement, self.achievement.pk, "description", "Tampered"),
        ]:
            original = getattr(model.objects.get(pk=pk), field)
            model.objects.filter(pk=pk).update(**{field: value})
            with self.subTest(model=model), self.assertRaises(ValidationError):
                self.issue()
            model.objects.filter(pk=pk).update(**{field: original})
        self.result.delete()
        with self.assertRaises(ValidationError):
            self.issue()
        finalization.refresh_from_db()
        self.assertEqual(
            finalization.payload_hash, hash_finalization_payload(finalization.payload)
        )
        self.assertFalse(Credential.objects.exists())

    def test_missing_issuer_rejected(self):
        self.event.organization = None
        self.event.organization_title = "Historical organizer"
        self.event.save()
        # A legacy commitment can exist without a current issuer organization.
        self.event.status = EventStatus.FINISHED
        self.event.save()
        payload = build_finalization_payload(self.event)
        EventFinalization.objects.create(
            event=self.event,
            payload=payload,
            payload_hash=hash_finalization_payload(payload),
            finalized_by=self.actor,
        )
        with self.assertRaises(ValidationError):
            self.issue()

    def test_issuance_atomic(self):
        self.finalize()
        with (
            patch.object(
                CredentialAchievement.objects,
                "bulk_create",
                side_effect=RuntimeError("storage failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.issue()
        self.assertFalse(Credential.objects.exists())
        self.assertFalse(CredentialAchievement.objects.exists())

    def test_all_services_reject_sealed_writes(self):
        self.finalize()
        operations = [
            lambda: EventService.remove_participant(
                event=self.event, participant_id=self.participant.pk
            ),
            lambda: EventService.add_achievement(
                event=self.event, validated_data={"title": "New", "kind": "other"}
            ),
            lambda: EventService.remove_achievement(
                event=self.event, achievement_id=self.achievement.pk
            ),
            lambda: EventService.award_achievement_to_participant(
                event=self.event,
                validated_data={
                    "participant": self.participant,
                    "achievement": self.achievement,
                },
            ),
            lambda: EventService.revoke_achievement_from_participant(
                event=self.event, participant_achievement_id=self.result.pk
            ),
        ]
        for index, operation in enumerate(operations):
            with self.subTest(operation=index), self.assertRaises(ValidationError):
                operation()
        self.assertTrue(
            EventParticipant.objects.filter(pk=self.participant.pk).exists()
        )
        self.assertTrue(
            EventAchievement.objects.filter(pk=self.achievement.pk).exists()
        )
        self.assertTrue(
            ParticipantAchievement.objects.filter(pk=self.result.pk).exists()
        )

    def test_finalization_service_requires_owner_or_admin(self):
        self.membership.role = "member"
        self.membership.save()
        with self.assertRaises(ValidationError):
            self.finalize()
        self.assertFalse(EventFinalization.objects.exists())
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.IN_PROGRESS)

    def test_stored_payload_tampering_rejected(self):
        finalization = self.finalize()
        finalization.payload["event"]["title"] = "Tampered snapshot"
        finalization.save(update_fields=["payload"])
        with self.assertRaises(ValidationError):
            self.issue()
        self.assertFalse(Credential.objects.exists())

    def test_schema_version_mismatch_rejected(self):
        finalization = self.finalize()
        for version in [None, 2]:
            payload = dict(finalization.payload)
            if version is None:
                payload.pop("schema_version")
            else:
                payload["schema_version"] = version
            EventFinalization.objects.filter(pk=finalization.pk).update(
                payload=payload, payload_hash=hash_finalization_payload(payload)
            )
            with (
                self.subTest(payload_version=version),
                self.assertRaises(ValidationError),
            ):
                self.issue()
        EventFinalization.objects.filter(pk=finalization.pk).update(
            payload=finalization.payload,
            payload_hash=finalization.payload_hash,
            schema_version=2,
        )
        with self.assertRaises(ValidationError):
            self.issue()
        self.assertFalse(Credential.objects.exists())

    def test_operational_metadata_does_not_change_commitment(self):
        finalization = self.finalize()
        EventParticipant.objects.filter(pk=self.participant.pk).update(
            user=self.actor, email="changed@example.com", source="import"
        )
        ParticipantAchievement.objects.filter(pk=self.result.pk).update(
            awarded_at=self.result.awarded_at + timedelta(days=1)
        )
        self.event.refresh_from_db()
        self.assertEqual(
            hash_finalization_payload(build_finalization_payload(self.event)),
            finalization.payload_hash,
        )
        credential = self.issue()
        self.assertEqual(credential.recipient_user, self.actor)

    def test_account_deletion_preserves_finalization(self):
        finalization = self.finalize()
        credential = self.issue()
        self.actor.delete()
        finalization.refresh_from_db()
        credential.refresh_from_db()
        self.assertIsNone(finalization.finalized_by)
        self.assertIsNone(credential.issued_by)
        self.assertEqual(credential.finalization, finalization)
        self.assertEqual(
            finalization.payload_hash, hash_finalization_payload(finalization.payload)
        )
