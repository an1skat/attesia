from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.events.models import (
    Event,
    EventParticipant,
    EventStatus,
    ParticipantSource,
)
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class EventParticipantAPITestCase(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@example.com", password="password123"
        )
        self.member = User.objects.create_user(
            email="member@example.com", password="password123"
        )
        self.participant_user = User.objects.create_user(
            email="participant@example.com",
            password="password123",
        )

        self.organization = Organization.objects.create(name="Test Org")
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
        )

        self.event = Event.objects.create(
            organization=self.organization,
            title="Test Event",
            status=EventStatus.PLANNED,
        )

        self.participants_url = reverse(
            "events:event_participant_list_create",
            kwargs={"event_id": self.event.pk},
        )

    def test_get_participants_success(self):
        EventParticipant.objects.create(
            event=self.event,
            name="John Doe",
            email="john@example.com",
        )
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.participants_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)

    def test_get_participants_unauthenticated_fails(self):
        response = self.client.get(self.participants_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_participants_non_existent_event_404(self):
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "events:event_participant_list_create",
            kwargs={"event_id": 99999},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_participant_by_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "user": self.participant_user.pk,
            "name": "Participant User",
            "email": "participant@example.com",
            "source": ParticipantSource.MANUAL,
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EventParticipant.objects.count(), 1)
        self.assertEqual(
            EventParticipant.objects.get().email, "participant@example.com"
        )

    def test_create_guest_participant_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Guest User",
            "email": "guest@example.com",
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        participant = EventParticipant.objects.get()
        self.assertIsNone(participant.user)
        self.assertEqual(participant.source, ParticipantSource.MANUAL)

    def test_create_participant_missing_name_or_email_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"name": "Only Name"}
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_create_participant_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {
            "name": "Guest User",
            "email": "guest@example.com",
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_guest_participant_returns_400(self):
        EventParticipant.objects.create(
            event=self.event,
            name="Guest User",
            email="guest@example.com",
        )
        self.client.force_authenticate(user=self.owner)
        payload = {
            "name": "Guest User",
            "email": "guest@example.com",
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_duplicate_user_participant_returns_400(self):
        EventParticipant.objects.create(
            event=self.event,
            user=self.participant_user,
            name="Participant User",
            email="participant@example.com",
        )
        self.client.force_authenticate(user=self.owner)
        payload = {
            "user": self.participant_user.pk,
            "name": "Participant User",
            "email": "participant@example.com",
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_participant_by_owner_success(self):
        participant = EventParticipant.objects.create(
            event=self.event,
            name="Guest User",
            email="guest@example.com",
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "events:event_participant_detail",
            kwargs={"event_id": self.event.pk, "pk": participant.pk},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(EventParticipant.objects.count(), 0)

    def test_delete_participant_by_regular_member_forbidden(self):
        participant = EventParticipant.objects.create(
            event=self.event,
            name="Guest User",
            email="guest@example.com",
        )
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "events:event_participant_detail",
            kwargs={"event_id": self.event.pk, "pk": participant.pk},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
