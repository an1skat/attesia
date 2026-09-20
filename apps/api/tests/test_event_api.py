from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.events.models import Event, EventStatus
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class EventAPITestCase(APITestCase):
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

        self.event_list_url = reverse("events:event_list")
        self.event_detail_url = reverse(
            "events:event_detail", kwargs={"pk": self.event.pk}
        )
        self.org_events_url = reverse(
            "events:organization_event_list_create",
            kwargs={"organization_id": self.organization.pk},
        )

    def test_get_all_events_anonymous_success(self):
        response = self.client.get(self.event_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)

    def test_get_all_events_pagination_structure(self):
        response = self.client.get(self.event_list_url)

        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_create_event_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "New Tech Conference",
            "description": "Annual meeting",
            "status": EventStatus.PLANNED,
        }

        response = self.client.post(self.org_events_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], payload["title"])
        self.assertEqual(response.data["organization_title"], self.organization.name)

    def test_create_event_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {"title": "Unauthorized Event", "status": EventStatus.PLANNED}

        response = self.client.post(self.org_events_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_event_by_anonymous_unauthorized(self):
        payload = {"title": "Anon Event", "status": EventStatus.PLANNED}

        response = self.client.post(self.org_events_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_event_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {"title": "Updated Event Title"}

        response = self.client.patch(self.event_detail_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], payload["title"])

        self.event.refresh_from_db()
        self.assertEqual(self.event.title, payload["title"])

    def test_patch_event_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)
        payload = {"title": "Hacked Title"}

        response = self.client.patch(self.event_detail_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_event_detail_success(self):
        response = self.client.get(self.event_detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.event.id)
        self.assertEqual(response.data["title"], self.event.title)

    def test_create_event_invalid_dates_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "Invalid Event",
            "status": EventStatus.PLANNED,
            "starts_at": "2026-10-10T12:00:00Z",
            "ends_at": "2026-10-09T12:00:00Z",
        }
        response = self.client.post(self.org_events_url, data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ends_at", response.data)

    def test_create_event_missing_status_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "No Status Event",
            "starts_at": "2026-10-10T12:00:00Z",
            "ends_at": "2026-10-10T14:00:00Z",
        }
        response = self.client.post(self.org_events_url, data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_get_events_non_existent_organization_returns_404(self):
        url = reverse(
            "events:organization_event_list_create", kwargs={"organization_id": 99999}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
