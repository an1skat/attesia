from typing import ClassVar

from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.events.api.v1.permissions import (
    IsOrganizationAdminOrOwnerOrReadOnly,
    # IsOrganizationAdminOrOwner,
    IsOrganizationMemberOrAdminForWrite,
)
from app.modules.events.api.v1.serializers import (
    EventAchievementCreateSerializer,
    EventAchievementSerializer,
    EventCreateSerializer,
    EventParticipantCreateSerializer,
    EventParticipantSerializer,
    EventSerializer,
    EventUpdateSerializer,
    ParticipantAchievementCreateSerializer,
    ParticipantAchievementSerializer,
)
from app.modules.events.selectors import (
    get_all_events,
    get_event_achievements,
    get_event_participants,
    get_events_by_organization,
    get_participant_achievement_from_event,
)
from app.modules.events.services import EventService
from app.modules.organizations.models import Organization


class EventPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


class EventListView(APIView, EventPagination):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def get(self, request):
        events = get_all_events()
        page = self.paginate_queryset(events, request, view=self)
        if page is not None:
            serializer = EventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EventSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventDetailView(APIView):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def get(self, request, pk):
        event = get_object_or_404(get_all_events(), pk=pk)
        serializer = EventSerializer(event)
        return Response(serializer.data)

    def patch(self, request, pk):
        event = get_object_or_404(get_all_events(), pk=pk)
        self.check_object_permissions(request, event)

        serializer = EventUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_event = EventService.update_event(
            event=event,
            validated_data=serializer.validated_data,
        )
        return Response(EventSerializer(update_event).data, status=status.HTTP_200_OK)


class OrganizationEventListView(APIView, EventPagination):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def get(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        events = get_events_by_organization(organization_id=organization.id)

        page = self.paginate_queryset(events, request, view=self)
        if page is not None:
            serializer = EventSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EventSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        self.check_object_permissions(request, organization)

        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event = EventService.create_event(
            organization=organization,
            validated_data=serializer.validated_data,
        )
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)


class EventParticipantListView(APIView, EventPagination):
    permission_classes: ClassVar[list] = [IsOrganizationMemberOrAdminForWrite]

    def get(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)
        participants = get_event_participants(event_id=event.id)

        page = self.paginate_queryset(participants, request, view=self)
        if page is not None:
            serializer = EventParticipantSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EventParticipantSerializer(participants, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        serializer = EventParticipantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant = EventService.add_participant(
            event=event,
            validated_data=serializer.validated_data,
        )
        return Response(
            EventParticipantSerializer(participant).data,
            status=status.HTTP_201_CREATED,
        )


class EventParticipantDetailView(APIView):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def delete(self, request, event_id, participant_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        EventService.remove_participant(
            event=event,
            participant_id=participant_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventAchievementListView(APIView, EventPagination):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def get(self, request, event_id):
        events = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, events)

        achievements = get_event_achievements(event_id=event_id)

        page = self.paginate_queryset(achievements, request, view=self)
        if page is not None:
            serializer = EventAchievementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EventAchievementSerializer(achievements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        serializer = EventAchievementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        achievement = EventService.add_achievement(
            event=event,
            validated_data=serializer.validated_data,
        )

        return Response(
            EventAchievementSerializer(achievement).data, status=status.HTTP_201_CREATED
        )


class EventAchievementDetailView(APIView):
    permission_classes: ClassVar[list] = [IsOrganizationAdminOrOwnerOrReadOnly]

    def delete(self, request, event_id, achievement_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        EventService.remove_achievement(
            event=event,
            achievement_id=achievement_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ParticipantAchievementListCreateView(APIView):
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsOrganizationAdminOrOwnerOrReadOnly,
    ]

    def get(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        achievements = get_participant_achievement_from_event(
            event=event,
            participant_id=request.query_params.get("participant_id"),
        )

        serializer = ParticipantAchievementSerializer(achievements, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        serializer = ParticipantAchievementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_achievement = EventService.award_achievement_to_participant(
            event=event,
            validated_data=serializer.validated_data,
        )
        output_serializer = ParticipantAchievementSerializer(participant_achievement)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ParticipantAchievementDetailView(APIView):
    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        IsOrganizationAdminOrOwnerOrReadOnly,
    ]

    def delete(self, request, event_id: int, pk: int):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        EventService.revoke_achievement_from_participant(
            event=event,
            participant_achievement_id=pk,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
