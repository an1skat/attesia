from typing import ClassVar

from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthAPICheck(APIView):
    permission_classes: ClassVar[list] = []
    authentication_classes: ClassVar[list] = []

    def get(self, request: Request, *args, **kwargs) -> Response:
        health_status = {
            "status": "healthy",
            "services": {
                "database": "unhealthy",
                "cache": "unhealthy",
            },
        }
        try:
            db_conn = connections["default"]
            db_conn.cursor()
            health_status["services"]["database"] = "healthy"
        except OperationalError:
            health_status["status"] = "unhealthy"

        try:
            cache.set("healthy_check_key", "ok", timeout=5)
            if cache.get("healthy_check_key") == "ok":
                health_status["services"]["cache"] = "healthy"
        except Exception:
            health_status["status"] = "unhealthy"

        if health_status["status"] == "healthy":
            return Response(health_status, status=status.HTTP_200_OK)

        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
