from typing import ClassVar

from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.events.api.v1.permissions import (
    IsOrganizationAdminOrOwnerOrReadOnly,
    # IsOrganizationAdminOrOwner,
    IsOrganizationMemberOrAdminForWrite,
)
from app.modules.events.api.v1.serializers import (
    EventCreateSerializer,
    EventParticipantCreateSerializer,
    EventParticipantSerializer,
    EventSerializer,
    EventUpdateSerializer,
)
from app.modules.events.selectors import (
    get_all_events,
    get_event_participants,
    get_events_by_organization,
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
