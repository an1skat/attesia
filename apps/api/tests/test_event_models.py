from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from app.modules.events.models import Event, EventStatus
from app.modules.organizations.models import Organization


class EventModelConstraintsTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Cybersec Corp")
        self.now = timezone.now()
        self.tomorrow = self.now + timezone.timedelta(days=1)
        self.yesterday = self.now - timezone.timedelta(days=1)

    def test_db_constraint_ends_at_before_starts_at_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            Event.objects.create(
                title="Invalid Dates Event",
                status=EventStatus.PLANNED,
                starts_at=self.now,
                ends_at=self.yesterday,
            )

    def test_db_constraint_invalid_status_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            Event.objects.create(
                title="Invalid Status Event",
                status="super_custom_status",
            )

    def test_db_constraint_allows_null_dates(self):
        event_null_end = Event.objects.create(
            title="Open End Event",
            status=EventStatus.PLANNED,
            starts_at=self.now,
            ends_at=None,
            organization_title="KPI",
        )
        self.assertIsNotNone(event_null_end.pk)

        event_null_both = Event.objects.create(
            title="TBD Dates Event",
            status=EventStatus.PLANNED,
            starts_at=None,
            ends_at=None,
            organization_title="KPI",
        )
        self.assertIsNotNone(event_null_both.pk)

    def test_clean_method_raises_validation_error_for_invalid_dates(self):
        event = Event(
            title="Validation Error Event",
            status=EventStatus.PLANNED,
            starts_at=self.now,
            ends_at=self.yesterday,
        )
        with self.assertRaises(ValidationError) as ctx:
            event.clean()

        self.assertIn("ends_at", ctx.exception.message_dict)

    def test_save_sets_organization_title_snapshot(self):
        event = Event.objects.create(
            title="Conf 2026",
            status=EventStatus.PLANNED,
            organization=self.organization,
        )
        self.assertEqual(event.organization_title, "Cybersec Corp")
        self.assertEqual(event.organization_display_name, "Cybersec Corp")

    def test_organization_display_name_fallback_when_organization_deleted(self):
        event = Event.objects.create(
            title="Historical Event",
            status=EventStatus.FINISHED,
            organization=self.organization,
        )

        self.organization.delete()
        event.refresh_from_db()

        self.assertIsNone(event.organization)
        self.assertEqual(event.organization_title, "Cybersec Corp")
        self.assertEqual(event.organization_display_name, "Cybersec Corp")

    def test_db_constraint_requires_organization_title_if_organization_is_null(self):
        valid_event = Event.objects.create(
            title="External Event",
            status=EventStatus.PLANNED,
            organization=None,
            organization_title="KPI",
        )
        self.assertIsNotNone(valid_event.pk)

        with self.assertRaises(IntegrityError):
            Event.objects.create(
                title="Orphan Event",
                status=EventStatus.PLANNED,
                organization=None,
                organization_title="",
            )
