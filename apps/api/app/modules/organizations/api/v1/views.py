from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.modules.organizations.selectors import get_user_organizations

from .serializers import OrganizationSerializer


class OrganizationView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        organizations = get_user_organizations(user=request.user)
        serializer = OrganizationSerializer(organizations, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OrganizationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
