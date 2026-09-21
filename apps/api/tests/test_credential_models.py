from django.contrib.auth import get_user_model
from django.test import TestCase

from app.modules.credentials.models import Credential, CredentialAchievement
from app.modules.events.models import Event, EventStatus
from app.modules.organizations.models import Organization

User = get_user_model()


class CredentialModelTestCase(TestCase):
    def setUp(self):
        self.issuer = User.objects.create_user(
            email="issuer@example.com",
            display_name="Issuer",
            password="password123",
        )
        self.recipient = User.objects.create_user(
            email="recipient@example.com",
            display_name="Recipient",
            password="password123",
        )

        self.organization = Organization.objects.create(name="KPI")

        self.event = Event.objects.create(
            title="Math Olympiad 2026",
            status=EventStatus.FINISHED,
            organization=self.organization,
        )

    def create_credential(self, **kwargs):
        defaults = {
            "organization": self.organization,
            "event": self.event,
            "recipient_user": self.recipient,
            "organization_title": self.organization.name,
            "event_title": self.event.title,
            "recipient_name": self.recipient.display_name,
            "issued_by": self.issuer,
        }
        defaults.update(kwargs)

        return Credential.objects.create(**defaults)

    def test_credential_generates_unique_public_id(self):
        first_credential = self.create_credential()
        second_credential = self.create_credential()

        self.assertIsNotNone(first_credential.public_id)
        self.assertIsNotNone(second_credential.public_id)
        self.assertNotEqual(
            first_credential.public_id,
            second_credential.public_id,
        )

    def test_credential_can_exist_without_recipient_user(self):
        credential = self.create_credential(
            recipient_user=None,
            recipient_name="John Smith",
        )

        self.assertIsNone(credential.recipient_user)
        self.assertEqual(credential.recipient_name, "John Smith")

    def test_deleting_organization_keeps_credential(self):
        credential = self.create_credential()
        credential_id = credential.pk

        self.organization.delete()

        credential = Credential.objects.get(pk=credential_id)

        self.assertIsNone(credential.organization)
        self.assertEqual(credential.organization_title, "KPI")

    def test_deleting_event_keeps_credential(self):
        credential = self.create_credential()
        credential_id = credential.pk

        self.event.delete()

        credential = Credential.objects.get(pk=credential_id)

        self.assertIsNone(credential.event)
        self.assertEqual(credential.event_title, "Math Olympiad 2026")

    def test_deleting_recipient_user_keeps_credential(self):
        credential = self.create_credential()
        credential_id = credential.pk

        self.recipient.delete()

        credential = Credential.objects.get(pk=credential_id)

        self.assertIsNone(credential.recipient_user)
        self.assertEqual(credential.recipient_name, "Recipient")

    def test_deleting_credential_deletes_achievement_snapshots(self):
        credential = self.create_credential()

        achievement = CredentialAchievement.objects.create(
            credential=credential,
            title="1st Place",
            description="Awarded for finishing in first place.",
        )
        achievement_id = achievement.pk

        credential.delete()

        self.assertFalse(
            CredentialAchievement.objects.filter(pk=achievement_id).exists()
        )

    def test_credential_can_have_multiple_achievements(self):
        credential = self.create_credential()

        CredentialAchievement.objects.create(
            credential=credential,
            title="1st Place",
        )
        CredentialAchievement.objects.create(
            credential=credential,
            title="Best Solution",
        )

        achievements = credential.achievement_snapshots.all()

        self.assertEqual(achievements.count(), 2)
        self.assertSetEqual(
            set(achievements.values_list("title", flat=True)),
            {"1st Place", "Best Solution"},
        )
