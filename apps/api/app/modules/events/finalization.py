import hashlib
import json
from datetime import UTC

from app.modules.events.models import ParticipantAchievement


def _datetime(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds") if value else None


def build_finalization_payload(event):
    """Schema 1: explicit fields, ID ordering, and UTC ISO-8601 datetimes."""
    return {
        "schema_version": 1,
        "event": {
            "id": event.pk,
            "title": event.title,
            "description": event.description,
            "status": event.status,
            "location": event.location,
            "starts_at": _datetime(event.starts_at),
            "ends_at": _datetime(event.ends_at),
            "organization_id": event.organization_id,
            "organization_title": event.organization_title,
        },
        "participants": list(event.participants.order_by("id").values("id", "name")),
        "event_achievements": list(
            event.event_achievements.order_by("id").values(
                "id", "title", "kind", "rank", "description"
            )
        ),
        "participant_achievements": [
            {
                "id": result.pk,
                "participant_id": result.participant_id,
                "achievement_id": result.achievement_id,
            }
            for result in ParticipantAchievement.objects.filter(
                participant__event=event
            ).order_by("id")
        ],
    }


def hash_finalization_payload(payload):
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
