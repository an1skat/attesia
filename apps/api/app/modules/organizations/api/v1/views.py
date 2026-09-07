from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.organizations.models import Organization
from app.modules.organizations.selectors import (
    get_organization_memberships,
    get_user_organizations,
)
from app.modules.organizations.services import add_organization_member

from .serializers import (
    OrganizationMembershipCreateSerializer,
    OrganizationMembershipSerializer,
    OrganizationSerializer,
)


class OrganizationDetailView(RetrieveAPIView):
    permission_classes = (AllowAny,)
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class MyOrganizationsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        organizations = get_user_organizations(user=request.user)
        serializer = OrganizationSerializer(organizations, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizationMembersView(APIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get(self, request, pk):
        try:
            memberships = get_organization_memberships(organization_id=pk)
        except Organization.DoesNotExist as exc:
            raise NotFound() from exc
        serializer = OrganizationMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        serializer = OrganizationMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = add_organization_member(
                actor=request.user, organization_id=pk, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            if exc.code in ("organization_not_found", "user_not_found"):
                raise NotFound(exc.message, code=exc.code) from exc
            raise ValidationError(exc.messages, code=exc.code) from exc
        return Response(
            OrganizationMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationPagination(PageNumberPagination):
    page_size = 20


class OrganizationListCreateView(ListCreateAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = Organization.objects.order_by("pk")
    serializer_class = OrganizationSerializer
    pagination_class = OrganizationPagination
    filter_backends = (SearchFilter,)
    search_fields = ("name",)
