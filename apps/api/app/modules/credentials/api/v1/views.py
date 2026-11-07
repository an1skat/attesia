from typing import ClassVar

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.credentials.api.v1.serializers import (
    CredentialFilterSerializer,
    CredentialIssueSerializer,
    CredentialRevokeSerializer,
    CredentialSerializer,
)
from app.modules.credentials.models import Credential
from app.modules.credentials.selectors import (
    get_credential_by_public_id,
    get_credentials_for_event,
)
from app.modules.credentials.services import CredentialService
from app.modules.events.models import EventParticipant, ParticipantAchievement
from app.modules.events.selectors import get_all_events
from app.modules.organizations.api.permissions import (
    IsOrganizationMemberOrAdminForWrite,
)


class CredentialPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100


def _serialize_for(credential: Credential, user) -> dict:
    # Re-read through the selector so snapshots come from the same ordered prefetch.
    credential = get_credential_by_public_id(public_id=credential.public_id, user=user)
    return CredentialSerializer(credential).data


class EventCredentialListCreateView(APIView, CredentialPagination):
    permission_classes: ClassVar[list] = [IsOrganizationMemberOrAdminForWrite]

    def get(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        filter_serializer = CredentialFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        credentials = get_credentials_for_event(
            event=event,
            participant_id=filter_serializer.validated_data.get("participant_id"),
        )
        page = self.paginate_queryset(credentials, request, view=self)
        if page is not None:
            serializer = CredentialSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = CredentialSerializer(credentials, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, event_id):
        event = get_object_or_404(get_all_events(), pk=event_id)
        self.check_object_permissions(request, event)

        serializer = CredentialIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        participant = EventParticipant.objects.filter(
            pk=data["participant_id"], event=event
        ).first()
        if participant is None:
            raise ValidationError(
                {"participant_id": "The participant does not belong to this event."}
            )

        # Resolve only rows inside the URL event; per-participant, finalization and
        # duplicate rules stay in CredentialService.issue_credential.
        ids = data["participant_achievement_ids"]
        resolved = ParticipantAchievement.objects.filter(
            pk__in=ids, participant__event=event
        ).in_bulk()
        if any(pk not in resolved for pk in ids):
            raise ValidationError(
                {
                    "participant_achievement_ids": "One or more achievements were not found in this event."
                }
            )

        credential = CredentialService.issue_credential(
            participant=participant,
            participant_achievements=[resolved[pk] for pk in ids],
            issued_by=request.user,
        )
        return Response(
            _serialize_for(credential, request.user), status=status.HTTP_201_CREATED
        )


class _CredentialObjectView(APIView):
    permission_classes: ClassVar[list] = [IsOrganizationMemberOrAdminForWrite]

    def get_object(self, request, public_id) -> Credential:
        try:
            credential = get_credential_by_public_id(
                public_id=public_id, user=request.user
            )
        except Credential.DoesNotExist as exc:
            raise NotFound from exc
        self.check_object_permissions(request, credential)
        return credential


class CredentialDetailView(_CredentialObjectView):
    def get(self, request, public_id):
        credential = self.get_object(request, public_id)
        return Response(CredentialSerializer(credential).data)


class CredentialRevokeView(_CredentialObjectView):
    def post(self, request, public_id):
        credential = self.get_object(request, public_id)

        serializer = CredentialRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        credential = CredentialService.revoke_credential(
            credential=credential,
            revoked_by=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(
            _serialize_for(credential, request.user), status=status.HTTP_200_OK
        )
