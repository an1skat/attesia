from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.events.models import (
    Event,
    EventAchievement,
    EventAchievementKind,
    EventStatus,
)
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class EventAchievementAPITestCase(APITestCase):
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

        self.achievement = EventAchievement.objects.create(
            event=self.event,
            title="1st Place",
            kind=EventAchievementKind.PLACE,
            rank=1,
            description="First place winner award",
        )

        self.achievement_list_url = reverse(
            "events:event_achievement_list",
            kwargs={"event_id": self.event.pk},
        )
        self.achievement_detail_url = reverse(
            "events:event_achievement_detail",
            kwargs={
                "event_id": self.event.pk,
                "achievement_id": self.achievement.pk,
            },
        )

    def test_get_achievements_by_organization_member_success(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.achievement_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.achievement.id)
        self.assertEqual(response.data["results"][0]["title"], "1st Place")
        self.assertEqual(
            response.data["results"][0]["kind"], EventAchievementKind.PLACE
        )
        self.assertEqual(response.data["results"][0]["rank"], 1)

    def test_get_achievements_anonymous_unauthorized(self):
        response = self.client.get(self.achievement_list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_achievements_pagination_structure(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.achievement_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_get_achievements_non_existent_event_returns_404(self):
        self.client.force_authenticate(user=self.member)
        url = reverse(
            "events:event_achievement_list",
            kwargs={"event_id": 99999},
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_achievement_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "2nd Place",
            "kind": EventAchievementKind.PLACE,
            "rank": 2,
            "description": "Second place runner up",
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], payload["title"])
        self.assertEqual(response.data["kind"], payload["kind"])
        self.assertEqual(response.data["rank"], payload["rank"])
        self.assertEqual(response.data["description"], payload["description"])

        self.assertTrue(
            EventAchievement.objects.filter(
                event=self.event, title="2nd Place", rank=2
            ).exists()
        )

    def test_add_achievement_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {
            "title": "Best UI/UX",
            "kind": EventAchievementKind.NOMINATION,
            "description": "Special design award",
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            EventAchievement.objects.filter(
                event=self.event, title="Best UI/UX"
            ).exists()
        )

    def test_add_achievement_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)
        payload = {
            "title": "Participation Certificate",
            "kind": EventAchievementKind.PARTICIPANT,
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_achievement_place_without_rank_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "Top Place",
            "kind": EventAchievementKind.PLACE,
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("rank", response.data)

    def test_add_achievement_duplicate_rank_for_place_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "Another 1st Place",
            "kind": EventAchievementKind.PLACE,
            "rank": 1,
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_achievement_nomination_resets_rank_to_none(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "Best Pitch",
            "kind": EventAchievementKind.NOMINATION,
            "rank": 5,
            "description": "Awarded for pitch presentation",
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["rank"])

    def test_add_achievement_invalid_kind_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "Super Award",
            "kind": "invalid_kind_type",
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kind", response.data)

    def test_add_achievement_missing_required_fields_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "description": "Only Description Provided",
        }

        response = self.client.post(self.achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
        self.assertIn("kind", response.data)

    def test_delete_achievement_by_organization_owner_success(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(self.achievement_detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            EventAchievement.objects.filter(id=self.achievement.id).exists()
        )

    def test_delete_achievement_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.delete(self.achievement_detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            EventAchievement.objects.filter(id=self.achievement.id).exists()
        )

    def test_delete_achievement_by_stranger_forbidden(self):
        self.client.force_authenticate(user=self.stranger)

        response = self.client.delete(self.achievement_detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            EventAchievement.objects.filter(id=self.achievement.id).exists()
        )

    def test_delete_non_existent_achievement_returns_404(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "events:event_achievement_detail",
            kwargs={"event_id": self.event.pk, "achievement_id": 99999},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_achievement_same_rank_different_events_success(self):
        second_event = Event.objects.create(
            title="Second Cyber Event",
            status=EventStatus.PLANNED,
            organization=self.organization,
        )
        second_event_achievement_list_url = reverse(
            "events:event_achievement_list",
            kwargs={"event_id": second_event.pk},
        )

        self.client.force_authenticate(user=self.owner)
        payload = {
            "title": "1st Place",
            "kind": EventAchievementKind.PLACE,
            "rank": 1,
            "description": "1st Place for second event",
        }

        response = self.client.post(second_event_achievement_list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rank"], 1)

        self.assertEqual(
            EventAchievement.objects.filter(
                kind=EventAchievementKind.PLACE, rank=1
            ).count(),
            2,
        )
        self.assertTrue(
            EventAchievement.objects.filter(event=self.event, rank=1).exists()
        )
        self.assertTrue(
            EventAchievement.objects.filter(event=second_event, rank=1).exists()
        )
