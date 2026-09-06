from rest_framework import status
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
from app.modules.organizations.selectors import get_user_organizations

from .serializers import OrganizationSerializer


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


class OrganizationPagination(PageNumberPagination):
    page_size = 20


class OrganizationListCreateView(ListCreateAPIView):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    queryset = Organization.objects.order_by("pk")
    serializer_class = OrganizationSerializer
    pagination_class = OrganizationPagination
    filter_backends = (SearchFilter,)
    search_fields = ("name",)
