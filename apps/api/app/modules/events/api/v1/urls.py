from django.urls import path

from app.modules.events.api.v1.views import (
    EventDetailView,
    EventListView,
    EventParticipantDetailView,
    EventParticipantListCreateView,
    OrganizationEventListView,
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
        EventParticipantListCreateView.as_view(),
        name="event_participant_list_create",
    ),
    path(
        "events/<int:event_id>/participants/<int:pk>/",
        EventParticipantDetailView.as_view(),
        name="event_participant_detail",
    ),
]
