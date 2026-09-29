from django.urls import path

from app.modules.events.api.v1.views import (
    EventAchievementDetailView,
    EventAchievementListView,
    EventDetailView,
    EventListView,
    EventParticipantDetailView,
    EventParticipantListView,
    OrganizationEventListView,
    ParticipantAchievementDetailView,
    ParticipantAchievementListCreateView,
)

app_name = "events"
urlpatterns = [
    path("events/", EventListView.as_view(), name="event_list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event_detail"),
    path(
        "organizations/<int:organization_id>/events/",
        OrganizationEventListView.as_view(),
        name="organization_event_list_create",
    ),
    path(
        "events/<int:event_id>/participants/",
        EventParticipantListView.as_view(),
        name="event_participant_list",
    ),
    path(
        "events/<int:event_id>/participants/<int:participant_id>/",
        EventParticipantDetailView.as_view(),
        name="event_participant_detail",
    ),
    path(
        "events/<int:event_id>/achievements/",
        EventAchievementListView.as_view(),
        name="event_achievement_list",
    ),
    path(
        "events/<int:event_id>/achievements/<int:achievement_id>/",
        EventAchievementDetailView.as_view(),
        name="event_achievement_detail",
    ),
    path(
        "events/<int:event_id>/participant-achievements/",
        ParticipantAchievementListCreateView.as_view(),
        name="participant_achievement_list",
    ),
    path(
        "events/<int:event_id>/participant-achievements/<int:pk>/",
        ParticipantAchievementDetailView.as_view(),
        name="participant_achievement_detail",
    ),
]
