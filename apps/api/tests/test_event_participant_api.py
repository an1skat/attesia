from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.events.models import (
    Event,
    EventParticipant,
    EventParticipantStatus,
    EventStatus,
)
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class EventParticipantAPITestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com",
            display_name="Owner User",
            password="password123",
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            display_name="Member User",
            password="password123",
        )
        self.stranger = User.objects.create_user(
            email="stranger@example.com",
            display_name="Stranger User",
            password="password123",
        )

        self.organization = Organization.objects.create(name="Cybersec Corp")

        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role="owner",
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role="member",
        )

        self.event = Event.objects.create(
            title="Initial Event",
            status=EventStatus.PLANNED,
            organization=self.organization,
        )

        self.participant = EventParticipant.objects.create(
            event=self.event,
            name="John Doe",
            email="john@example.com",
            source=EventParticipantStatus.MANUAL,
        )

        self.participant_list_url = reverse(
            "events:event_participant_list",
            kwargs={"event_id": self.event.pk},
        )
        self.participant_detail_url = reverse(
            "events:event_participant_detail",
            kwargs={
                "event_id": self.event.pk,
                "participant_id": self.participant.pk,
            },
        )

    def test_get_participants_anonymous_success(self):
        response = self.client.get(self.participant_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.participant.id)
        self.assertEqual(response.data["results"][0]["email"], "john@example.com")

    def test_get_participants_pagination_structure(self):
        response = self.client.get(self.participant_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_get_participants_non_existent_event_returns_404(self):
        url = reverse(
            "events:event_participant_list",
            kwargs={"event_id": 99999},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_participant_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Alice Smith",
            "email": "alice@example.com",
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], payload["name"])
        self.assertEqual(response.data["email"], payload["email"])
        self.assertEqual(response.data["source"], EventParticipantStatus.MANUAL)

        self.assertTrue(
            EventParticipant.objects.filter(
                event=self.event, email="alice@example.com"
            ).exists()
        )

    def test_add_participant_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {
            "name": "Bob Marley",
            "email": "bob@example.com",
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            EventParticipant.objects.filter(
                event=self.event, email="bob@example.com"
            ).exists()
        )

    def test_add_participant_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)
        payload = {
            "name": "Stranger Danger",
            "email": "stranger_p@example.com",
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_participant_duplicate_email_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Duplicate Person",
            "email": self.participant.email.upper(),
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_add_participant_invalid_email_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Invalid Email",
            "email": "not-an-email",
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_add_participant_missing_required_fields_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Only Name User",
        }

        response = self.client.post(self.participant_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_delete_participant_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(self.participant_detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            EventParticipant.objects.filter(id=self.participant.id).exists()
        )

    def test_delete_participant_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.delete(self.participant_detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            EventParticipant.objects.filter(id=self.participant.id).exists()
        )

    def test_delete_participant_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)

        response = self.client.delete(self.participant_detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            EventParticipant.objects.filter(id=self.participant.id).exists()
        )

    def test_delete_non_existent_participant_returns_400_or_404(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "events:event_participant_detail",
            kwargs={"event_id": self.event.pk, "participant_id": 99999},
        )

        response = self.client.delete(url)

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND],
        )
