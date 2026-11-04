import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.credentials.services import CredentialService
from app.modules.events.models import (
    Event,
    EventAchievement,
    EventParticipant,
    EventStatus,
    ParticipantAchievement,
)
from app.modules.events.services import EventService
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class CredentialAPITestBase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", display_name="Owner"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", display_name="Admin"
        )
        self.member = User.objects.create_user(
            email="member@example.com", display_name="Member"
        )
        self.stranger = User.objects.create_user(
            email="stranger@example.com", display_name="Stranger"
        )
        self.organization = Organization.objects.create(name="Organizer")
        for user, role in [
            (self.owner, "owner"),
            (self.admin, "admin"),
            (self.member, "member"),
        ]:
            OrganizationMembership.objects.create(
                organization=self.organization, user=user, role=role
            )

        self.event = Event.objects.create(
            title="Main Hackathon",
            organization=self.organization,
            status=EventStatus.IN_PROGRESS,
        )
        self.participant = EventParticipant.objects.create(
            event=self.event, name="Alice", email="alice@example.com"
        )
        self.other_participant = EventParticipant.objects.create(
            event=self.event, name="Bob", email="bob@example.com"
        )
        self.winner = EventAchievement.objects.create(
            event=self.event,
            title="Winner",
            description="First place",
            kind="place",
            rank=1,
        )
        self.finalist = EventAchievement.objects.create(
            event=self.event, title="Finalist", kind="finalist"
        )
        self.alice_winner = ParticipantAchievement.objects.create(
            participant=self.participant, achievement=self.winner
        )
        self.alice_finalist = ParticipantAchievement.objects.create(
            participant=self.participant, achievement=self.finalist
        )
        self.bob_finalist = ParticipantAchievement.objects.create(
            participant=self.other_participant, achievement=self.finalist
        )
        self.finalization = EventService.finalize_event(
            event=self.event, finalized_by=self.owner
        )
        self.event.refresh_from_db()

        self.list_url = reverse(
            "credentials:event_credential_list", kwargs={"event_id": self.event.pk}
        )

    def issue(self, participant=None, results=None):
        return CredentialService.issue_credential(
            participant=participant or self.participant,
            participant_achievements=results or [self.alice_winner],
            issued_by=self.owner,
        )

    def detail_url(self, credential):
        public_id = getattr(credential, "public_id", credential)
        return reverse("credentials:credential_detail", kwargs={"public_id": public_id})

    def revoke_url(self, credential):
        return reverse(
            "credentials:credential_revoke",
            kwargs={"public_id": credential.public_id},
        )

    def payload(self, achievement_ids=None, participant=None):
        return {
            "participant_id": (participant or self.participant).pk,
            "participant_achievement_ids": (
                [self.alice_winner.pk, self.alice_finalist.pk]
                if achievement_ids is None
                else achievement_ids
            ),
        }


class CredentialIssueAPITests(CredentialAPITestBase):
    def test_owner_and_admin_can_issue(self):
        for user in [self.owner, self.admin]:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.post(
                    self.list_url, self.payload(), format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                credential = Credential.objects.get(
                    public_id=response.data["public_id"]
                )
                self.assertEqual(credential.issued_by, user)
                self.assertEqual(response.data["issued_by"], user.pk)

    def test_member_stranger_and_anonymous_cannot_issue(self):
        for user, expected in [
            (self.member, status.HTTP_403_FORBIDDEN),
            (self.stranger, status.HTTP_403_FORBIDDEN),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]:
            with self.subTest(user=getattr(user, "email", "anonymous")):
                self.client.force_authenticate(user)
                response = self.client.post(
                    self.list_url, self.payload(), format="json"
                )
                self.assertEqual(response.status_code, expected)
        self.assertFalse(Credential.objects.exists())

    def test_unknown_event_returns_404(self):
        self.client.force_authenticate(self.owner)
        url = reverse("credentials:event_credential_list", kwargs={"event_id": 999_999})
        response = self.client.post(url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_participant_must_belong_to_url_event(self):
        other_event = Event.objects.create(
            title="Other", organization=self.organization, status="in_progress"
        )
        foreign = EventParticipant.objects.create(
            event=other_event, name="Foreign", email="foreign@example.com"
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.list_url,
            self.payload(participant=foreign),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("participant_id", response.data)
        self.assertFalse(Credential.objects.exists())

    def test_empty_or_missing_achievement_list_rejected(self):
        self.client.force_authenticate(self.owner)
        for body in [
            self.payload(achievement_ids=[]),
            {"participant_id": self.participant.pk},
        ]:
            with self.subTest(body=body):
                response = self.client.post(self.list_url, body, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("participant_achievement_ids", response.data)
        self.assertFalse(Credential.objects.exists())

    def test_invalid_cross_participant_and_duplicate_achievements_rejected(self):
        other_org = Organization.objects.create(name="Other org")
        other_event = Event.objects.create(
            title="Other", organization=other_org, status="in_progress"
        )
        foreign_participant = EventParticipant.objects.create(
            event=other_event, name="Foreign", email="foreign@example.com"
        )
        foreign_result = ParticipantAchievement.objects.create(
            participant=foreign_participant,
            achievement=EventAchievement.objects.create(
                event=other_event, title="Foreign"
            ),
        )
        self.client.force_authenticate(self.owner)
        for ids in [
            [999_999],
            [foreign_result.pk],
            [self.bob_finalist.pk],
            [self.alice_winner.pk, self.bob_finalist.pk],
            [self.alice_winner.pk, self.alice_winner.pk],
        ]:
            with self.subTest(ids=ids):
                response = self.client.post(
                    self.list_url, self.payload(achievement_ids=ids), format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Credential.objects.exists())

    def test_server_derived_fields_are_not_accepted(self):
        self.client.force_authenticate(self.owner)
        for field, value in [
            ("organization", self.organization.pk),
            ("organization_title", "Forged"),
            ("event_title", "Forged"),
            ("recipient_name", "Forged"),
            ("recipient_user", self.stranger.pk),
            ("issued_by", self.stranger.pk),
            ("finalization", 1),
            ("achievements", [{"title": "Forged"}]),
        ]:
            with self.subTest(field=field):
                body = {**self.payload(), field: value}
                response = self.client.post(self.list_url, body, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertFalse(Credential.objects.exists())

    def test_unfinished_event_rejected_by_service(self):
        event = Event.objects.create(
            title="Running", organization=self.organization, status="in_progress"
        )
        participant = EventParticipant.objects.create(
            event=event, name="Carol", email="carol@example.com"
        )
        result = ParticipantAchievement.objects.create(
            participant=participant,
            achievement=EventAchievement.objects.create(event=event, title="Award"),
        )
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            reverse("credentials:event_credential_list", kwargs={"event_id": event.pk}),
            self.payload(achievement_ids=[result.pk], participant=participant),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Credential.objects.exists())

    def test_response_contains_snapshots(self):
        self.participant.user = self.member
        self.participant.save(update_fields=["user"])
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data
        self.assertEqual(
            set(data),
            {
                "public_id",
                "organization",
                "organization_title",
                "event",
                "event_title",
                "participant",
                "recipient_user",
                "recipient_name",
                "achievements",
                "finalization",
                "issued_by",
                "issued_at",
                "revoked_at",
                "revoked_by",
                "revocation_reason",
            },
        )
        self.assertEqual(data["organization"], self.organization.pk)
        self.assertEqual(data["organization_title"], "Organizer")
        self.assertEqual(data["event"], self.event.pk)
        self.assertEqual(data["event_title"], "Main Hackathon")
        self.assertEqual(data["participant"], self.participant.pk)
        self.assertEqual(data["recipient_user"], self.member.pk)
        self.assertEqual(data["recipient_name"], "Alice")
        self.assertIsNone(data["revoked_at"])
        self.assertEqual(
            set(data["finalization"]), {"version", "schema_version", "finalized_at"}
        )
        self.assertEqual(
            [dict(item) for item in data["achievements"]],
            [
                {
                    "title": "Winner",
                    "description": "First place",
                    "kind": "place",
                    "rank": 1,
                },
                {
                    "title": "Finalist",
                    "description": "",
                    "kind": "finalist",
                    "rank": None,
                },
            ],
        )

    def test_participant_may_receive_multiple_credentials(self):
        self.client.force_authenticate(self.owner)
        for ids in [[self.alice_winner.pk], [self.alice_finalist.pk]]:
            response = self.client.post(
                self.list_url, self.payload(achievement_ids=ids), format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Credential.objects.filter(participant=self.participant).count(), 2
        )


class CredentialListAPITests(CredentialAPITestBase):
    def test_owner_admin_member_can_list(self):
        credential = self.issue()
        for user in [self.owner, self.admin, self.member]:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["public_id"], str(credential.public_id)
                )

    def test_stranger_and_anonymous_cannot_list(self):
        self.issue()
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_list_is_scoped_to_url_event(self):
        self.issue()
        other_event = Event.objects.create(
            title="Other", organization=self.organization, status="in_progress"
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            reverse(
                "credentials:event_credential_list",
                kwargs={"event_id": other_event.pk},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_pagination(self):
        for _ in range(32):
            self.issue()
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 32)
        self.assertEqual(len(response.data["results"]), 30)
        self.assertIsNotNone(response.data["next"])
        response = self.client.get(self.list_url, {"page": 2})
        self.assertEqual(len(response.data["results"]), 2)
        response = self.client.get(self.list_url, {"page_size": 500})
        self.assertEqual(len(response.data["results"]), 32)
        response = self.client.get(self.list_url, {"page_size": 5})
        self.assertEqual(len(response.data["results"]), 5)

    def test_max_page_size_is_100(self):
        credential = self.issue()
        snapshot = credential.achievement_snapshots.get()
        for _ in range(104):
            clone = Credential.objects.create(
                organization=self.organization,
                organization_title=credential.organization_title,
                event=self.event,
                event_title=credential.event_title,
                participant=self.participant,
                recipient_name=credential.recipient_name,
                finalization=credential.finalization,
                issued_by=self.owner,
            )
            CredentialAchievement.objects.create(credential=clone, title=snapshot.title)
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url, {"page_size": 1000})
        self.assertEqual(response.data["count"], 105)
        self.assertEqual(len(response.data["results"]), 100)

    def test_participant_id_filter(self):
        alice = self.issue()
        bob = self.issue(
            participant=self.other_participant, results=[self.bob_finalist]
        )
        self.client.force_authenticate(self.member)
        for participant, expected in [
            (self.participant, alice),
            (self.other_participant, bob),
        ]:
            with self.subTest(participant=participant.name):
                response = self.client.get(
                    self.list_url, {"participant_id": participant.pk}
                )
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(
                    response.data["results"][0]["public_id"], str(expected.public_id)
                )
        self.assertEqual(self.client.get(self.list_url).data["count"], 2)
        self.assertEqual(
            self.client.get(self.list_url, {"participant_id": "abc"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_revoked_credentials_remain_in_list(self):
        credential = self.issue()
        CredentialService.revoke_credential(
            credential=credential, revoked_by=self.owner, reason="Mistake"
        )
        self.client.force_authenticate(self.member)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNotNone(response.data["results"][0]["revoked_at"])
        self.assertEqual(response.data["results"][0]["revocation_reason"], "Mistake")

    def test_list_query_count_does_not_grow_with_credentials(self):
        for _ in range(5):
            self.issue(results=[self.alice_winner, self.alice_finalist])
        self.client.force_authenticate(self.member)
        # membership check + event + count + credentials (joined finalization)
        # + snapshots
        with self.assertNumQueries(5):
            response = self.client.get(self.list_url)
        self.assertEqual(len(response.data["results"]), 5)
        for item in response.data["results"]:
            self.assertEqual(item["finalization"]["version"], 1)


class CredentialDetailAPITests(CredentialAPITestBase):
    def test_lookup_uses_public_id(self):
        credential = self.issue()
        self.client.force_authenticate(self.member)
        response = self.client.get(self.detail_url(credential))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["public_id"], str(credential.public_id))
        self.assertNotIn("id", response.data)
        self.assertEqual(
            self.client.get(f"/api/v1/credentials/{credential.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(self.detail_url(uuid.uuid4())).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_organization_members_can_read(self):
        credential = self.issue()
        for user in [self.owner, self.admin, self.member]:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                self.assertEqual(
                    self.client.get(self.detail_url(credential)).status_code,
                    status.HTTP_200_OK,
                )

    def test_stranger_and_anonymous_cannot_read(self):
        credential = self.issue()
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(self.detail_url(credential)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(self.detail_url(credential)).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_member_of_other_organization_cannot_read(self):
        credential = self.issue()
        other_org = Organization.objects.create(name="Other org")
        OrganizationMembership.objects.create(
            organization=other_org, user=self.stranger, role="owner"
        )
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.get(self.detail_url(credential)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                self.revoke_url(credential), {"reason": "x"}, format="json"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_credential_without_organization_is_not_exposed(self):
        credential = self.issue()
        Credential.objects.filter(pk=credential.pk).update(organization=None)
        for user in [self.owner, self.member, self.stranger]:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                self.assertEqual(
                    self.client.get(self.detail_url(credential)).status_code,
                    status.HTTP_404_NOT_FOUND,
                )

    def test_achievement_snapshots_returned(self):
        credential = self.issue(results=[self.alice_winner, self.alice_finalist])
        self.client.force_authenticate(self.member)
        response = self.client.get(self.detail_url(credential))
        self.assertEqual(
            [item["title"] for item in response.data["achievements"]],
            ["Winner", "Finalist"],
        )
        self.assertEqual(
            set(response.data["achievements"][0]),
            {"title", "description", "kind", "rank"},
        )

    def test_historical_snapshot_fields_used(self):
        credential = self.issue()
        Organization.objects.filter(pk=self.organization.pk).update(name="Renamed org")
        Event.objects.filter(pk=self.event.pk).update(title="Renamed event")
        EventParticipant.objects.filter(pk=self.participant.pk).update(
            name="Renamed person"
        )
        EventAchievement.objects.filter(pk=self.winner.pk).update(
            title="Renamed award", description="Changed", rank=2
        )
        self.client.force_authenticate(self.member)
        data = self.client.get(self.detail_url(credential)).data
        self.assertEqual(data["organization_title"], "Organizer")
        self.assertEqual(data["event_title"], "Main Hackathon")
        self.assertEqual(data["recipient_name"], "Alice")
        self.assertEqual(
            dict(data["achievements"][0]),
            {
                "title": "Winner",
                "description": "First place",
                "kind": "place",
                "rank": 1,
            },
        )


class CredentialFinalizationOutputTests(CredentialAPITestBase):
    def test_finalization_summary_returned_without_crypto_surface(self):
        credential = self.issue()
        self.client.force_authenticate(self.member)
        for data in [
            self.client.get(self.detail_url(credential)).data,
            self.client.get(self.list_url).data["results"][0],
        ]:
            self.assertEqual(
                dict(data["finalization"]),
                {
                    "version": self.finalization.version,
                    "schema_version": self.finalization.schema_version,
                    "finalized_at": self.finalization.finalized_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                },
            )
            self.assertNotIn("payload", data["finalization"])
            self.assertNotIn("payload_hash", data["finalization"])

    def test_issue_response_includes_finalization(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["finalization"]["version"], 1)
        self.assertEqual(response.data["finalization"]["schema_version"], 1)

    def test_detail_query_count(self):
        credential = self.issue(results=[self.alice_winner, self.alice_finalist])
        self.client.force_authenticate(self.member)
        # credential (joined finalization, scoped by membership) + snapshots
        # + organization and membership lookups from the object permission check
        with self.assertNumQueries(4):
            response = self.client.get(self.detail_url(credential))
        self.assertEqual(response.data["finalization"]["version"], 1)

    def test_missing_finalization_serializes_as_null(self):
        credential = self.issue()
        Credential.objects.filter(pk=credential.pk).update(finalization=None)
        self.client.force_authenticate(self.member)
        response = self.client.get(self.detail_url(credential))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["finalization"])


class CredentialRevokeAPITests(CredentialAPITestBase):
    def test_owner_and_admin_can_revoke(self):
        for user in [self.owner, self.admin]:
            with self.subTest(user=user.email):
                credential = self.issue()
                self.client.force_authenticate(user)
                before = timezone.now()
                response = self.client.post(
                    self.revoke_url(credential),
                    {"reason": "  Issued by mistake  "},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                credential.refresh_from_db()
                self.assertIsNotNone(credential.revoked_at)
                self.assertTrue(timezone.is_aware(credential.revoked_at))
                self.assertLessEqual(before, credential.revoked_at)
                self.assertLess(credential.revoked_at - before, timedelta(minutes=1))
                self.assertEqual(credential.revoked_by, user)
                self.assertEqual(credential.revocation_reason, "Issued by mistake")
                self.assertEqual(response.data["revoked_by"], user.pk)
                self.assertEqual(
                    response.data["revocation_reason"], "Issued by mistake"
                )

    def test_member_stranger_anonymous_cannot_revoke(self):
        credential = self.issue()
        for user, expected in [
            (self.member, status.HTTP_403_FORBIDDEN),
            (self.stranger, status.HTTP_404_NOT_FOUND),
            (None, status.HTTP_401_UNAUTHORIZED),
        ]:
            with self.subTest(user=getattr(user, "email", "anonymous")):
                self.client.force_authenticate(user)
                response = self.client.post(
                    self.revoke_url(credential), {"reason": "No"}, format="json"
                )
                self.assertEqual(response.status_code, expected)
        credential.refresh_from_db()
        self.assertIsNone(credential.revoked_at)

    def test_reason_required_and_whitespace_rejected(self):
        credential = self.issue()
        self.client.force_authenticate(self.owner)
        for body in [{}, {"reason": ""}, {"reason": "   \n\t "}]:
            with self.subTest(body=body):
                response = self.client.post(
                    self.revoke_url(credential), body, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("reason", response.data)
        credential.refresh_from_db()
        self.assertIsNone(credential.revoked_at)
        self.assertEqual(credential.revocation_reason, "")

    def test_second_revoke_rejected(self):
        credential = self.issue()
        self.client.force_authenticate(self.owner)
        url = self.revoke_url(credential)
        self.assertEqual(
            self.client.post(url, {"reason": "First"}, format="json").status_code,
            status.HTTP_200_OK,
        )
        credential.refresh_from_db()
        first_revoked_at = credential.revoked_at
        self.client.force_authenticate(self.admin)
        response = self.client.post(url, {"reason": "Second"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        credential.refresh_from_db()
        self.assertEqual(credential.revoked_at, first_revoked_at)
        self.assertEqual(credential.revoked_by, self.owner)
        self.assertEqual(credential.revocation_reason, "First")

    def test_snapshots_unchanged_and_still_readable(self):
        credential = self.issue(results=[self.alice_winner, self.alice_finalist])
        snapshot_fields = ("title", "description", "kind", "rank")
        credential_fields = (
            "organization_title",
            "event_title",
            "recipient_name",
            "issued_at",
            "issued_by_id",
            "participant_id",
            "finalization_id",
        )
        before_credential = Credential.objects.values(*credential_fields).get(
            pk=credential.pk
        )
        before_snapshots = list(
            credential.achievement_snapshots.order_by("id").values(*snapshot_fields)
        )
        self.client.force_authenticate(self.owner)
        self.client.post(self.revoke_url(credential), {"reason": "x"}, format="json")

        self.assertEqual(
            Credential.objects.values(*credential_fields).get(pk=credential.pk),
            before_credential,
        )
        self.assertEqual(
            list(
                credential.achievement_snapshots.order_by("id").values(*snapshot_fields)
            ),
            before_snapshots,
        )
        self.client.force_authenticate(self.member)
        detail = self.client.get(self.detail_url(credential))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(detail.data["revoked_at"])
        self.assertEqual(len(detail.data["achievements"]), 2)
        self.assertEqual(self.client.get(self.list_url).data["count"], 1)

    def test_revoke_endpoint_rejects_get_and_no_delete_endpoint(self):
        credential = self.issue()
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.get(self.revoke_url(credential)).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(self.detail_url(credential)).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertTrue(Credential.objects.filter(pk=credential.pk).exists())


class CredentialRevokeServiceTests(CredentialAPITestBase):
    def test_service_rules(self):
        credential = self.issue()
        for user, reason in [
            (self.member, "Reason"),
            (self.stranger, "Reason"),
            (self.owner, "   "),
            (self.owner, None),
        ]:
            with (
                self.subTest(user=user.email, reason=reason),
                self.assertRaises(ValidationError),
            ):
                CredentialService.revoke_credential(
                    credential=credential, revoked_by=user, reason=reason
                )
        revoked = CredentialService.revoke_credential(
            credential=credential, revoked_by=self.admin, reason=" Done "
        )
        self.assertEqual(revoked.revocation_reason, "Done")
        self.assertEqual(revoked.revoked_by, self.admin)
        with self.assertRaises(ValidationError):
            CredentialService.revoke_credential(
                credential=credential, revoked_by=self.owner, reason="Again"
            )

    def test_stale_instance_cannot_revoke_twice(self):
        credential = self.issue()
        stale = Credential.objects.get(pk=credential.pk)
        CredentialService.revoke_credential(
            credential=credential, revoked_by=self.owner, reason="First"
        )
        self.assertIsNone(stale.revoked_at)
        with self.assertRaises(ValidationError):
            CredentialService.revoke_credential(
                credential=stale, revoked_by=self.admin, reason="Second"
            )
        credential.refresh_from_db()
        self.assertEqual(credential.revocation_reason, "First")

    def test_credential_without_organization_cannot_be_revoked(self):
        credential = self.issue()
        Credential.objects.filter(pk=credential.pk).update(organization=None)
        with self.assertRaises(ValidationError):
            CredentialService.revoke_credential(
                credential=credential, revoked_by=self.owner, reason="Reason"
            )
