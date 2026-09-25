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
        self.stranger = User.objects.create_user(
            email="stranger@example.com", password="password123"
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

    def test_get_participants_by_member_success(self):
        EventParticipant.objects.create(
            event=self.event, name="John Doe", email="john@example.com"
        )
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.participants_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_get_participants_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(self.participants_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_participants_unauthenticated_unauthorized(self):
        response = self.client.get(self.participants_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_participant_by_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"name": "External Guest", "email": "guest@example.com"}
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(EventParticipant.objects.count(), 1)

        participant = EventParticipant.objects.get()
        self.assertEqual(participant.name, "External Guest")
        self.assertEqual(participant.email, "guest@example.com")
        self.assertEqual(participant.source, ParticipantSource.MANUAL)

    def test_create_participant_linked_to_user_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "user": self.member.pk,
            "name": "Member User",
            "email": self.member.email,
        }
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        participant = EventParticipant.objects.get()
        self.assertEqual(participant.user, self.member)

    def test_create_participant_by_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {"name": "Guest", "email": "guest@example.com"}
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_participant_fails(self):
        EventParticipant.objects.create(
            event=self.event, name="Guest", email="guest@example.com"
        )
        self.client.force_authenticate(user=self.owner)
        payload = {"name": "Guest Duplicate", "email": "guest@example.com"}
        response = self.client.post(self.participants_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_participant_by_owner_success(self):
        participant = EventParticipant.objects.create(
            event=self.event, name="Guest", email="guest@example.com"
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "events:event_participant_detail",
            kwargs={"event_id": self.event.pk, "pk": participant.pk},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(EventParticipant.objects.count(), 0)

    def test_delete_participant_by_member_forbidden(self):
        participant = EventParticipant.objects.create(
            event=self.event, name="Guest", email="guest@example.com"
        )
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "events:event_participant_detail",
            kwargs={"event_id": self.event.pk, "pk": participant.pk},
        )
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
