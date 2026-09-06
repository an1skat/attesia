from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
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


class OrganizationCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = OrganizationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
