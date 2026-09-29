from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.modules.events.models import (
    Event,
    EventAchievement,
    EventAchievementKind,
    EventParticipant,
    EventStatus,
    ParticipantAchievement,
)
from app.modules.organizations.models import Organization, OrganizationMembership

User = get_user_model()


class ParticipantAchievementAPITestCase(APITestCase):
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
            title="Main Hackathon",
            status=EventStatus.PLANNED,
            organization=self.organization,
        )

        self.participant = EventParticipant.objects.create(
            event=self.event,
            name="Alice",
            email="alice@example.com",
        )

        self.achievement = EventAchievement.objects.create(
            event=self.event,
            title="1st Place",
            kind=EventAchievementKind.PLACE,
            rank=1,
        )

        self.participant_achievement = ParticipantAchievement.objects.create(
            participant=self.participant,
            achievement=self.achievement,
        )

        self.list_url = reverse(
            "events:participant_achievement_list",
            kwargs={"event_id": self.event.pk},
        )
        self.detail_url = reverse(
            "events:participant_achievement_detail",
            kwargs={
                "event_id": self.event.pk,
                "pk": self.participant_achievement.pk,
            },
        )

    def test_get_participant_achievements_by_member_success(self):
        self.client.force_authenticate(user=self.member)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["participant"], self.participant.id)
        self.assertEqual(response.data[0]["achievement"], self.achievement.id)
        self.assertEqual(response.data[0]["participant_name"], "Alice")
        self.assertEqual(response.data[0]["achievement_title"], "1st Place")

    def test_get_participant_achievements_anonymous_unauthorized(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_participant_achievements_filter_by_participant(self):
        second_participant = EventParticipant.objects.create(
            event=self.event,
            name="Bob",
            email="bob@example.com",
        )
        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            f"{self.list_url}?participant_id={second_participant.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_award_achievement_by_owner_success(self):
        new_participant = EventParticipant.objects.create(
            event=self.event,
            name="Charlie",
            email="charlie@example.com",
        )
        self.client.force_authenticate(user=self.owner)
        payload = {
            "participant": new_participant.id,
            "achievement": self.achievement.id,
        }

        response = self.client.post(self.list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["participant"], new_participant.id)
        self.assertTrue(
            ParticipantAchievement.objects.filter(
                participant=new_participant, achievement=self.achievement
            ).exists()
        )

    def test_award_achievement_duplicate_returns_400(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "participant": self.participant.id,
            "achievement": self.achievement.id,
        }

        response = self.client.post(self.list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_award_achievement_by_regular_member_forbidden(self):
        self.client.force_authenticate(user=self.member)
        payload = {
            "participant": self.participant.id,
            "achievement": self.achievement.id,
        }

        response = self.client.post(self.list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_award_achievement_cross_event_returns_400(self):
        other_event = Event.objects.create(
            title="Other Event",
            status=EventStatus.PLANNED,
            organization=self.organization,
        )
        other_participant = EventParticipant.objects.create(
            event=other_event,
            name="Outsider Participant",
            email="outsider@example.com",
        )

        self.client.force_authenticate(user=self.owner)
        payload = {
            "participant": other_participant.id,
            "achievement": self.achievement.id,
        }

        response = self.client.post(self.list_url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoke_achievement_by_owner_success(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ParticipantAchievement.objects.filter(
                id=self.participant_achievement.id
            ).exists()
        )

    def test_revoke_achievement_by_member_forbidden(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            ParticipantAchievement.objects.filter(
                id=self.participant_achievement.id
            ).exists()
        )

    def test_revoke_non_existent_achievement_returns_404(self):
        self.client.force_authenticate(user=self.owner)
        invalid_url = reverse(
            "events:participant_achievement_detail",
            kwargs={"event_id": self.event.pk, "pk": 99999},
        )

        response = self.client.delete(invalid_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
