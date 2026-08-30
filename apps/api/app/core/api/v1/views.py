from typing import ClassVar

from django.core.cache import cache
from django.db import connections
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthAPICheck(APIView):
    permission_classes: ClassVar[list] = []
    authentication_classes: ClassVar[list] = []

    db_connection = connections["default"]
    cache_provider = cache

    def get(self, request: Request, *args, **kwargs) -> Response:
        services = {
            "database": "healthy",
            "cache": "healthy",
        }
        is_healthy = True

        try:
            if not self.db_connection.is_usable():
                is_healthy = False
                services["database"] = "unhealthy"
        except Exception:
            services["database"] = "unhealthy"
            is_healthy = False

        try:
            if hasattr(self.cache_provider, "ping") and callable(
                self.cache_provider.ping
            ):
                self.cache_provider.ping()
            else:
                self.cache_provider.set("healthy_cache_key", "ok", timeout=5)
                if self.cache_provider.get("healthy_cache_key") != "ok":
                    raise ValueError("Cache read/write failed")
        except Exception:
            services["cache"] = "unhealthy"
            is_healthy = False

        response_data = {
            "status": "healthy" if is_healthy else "unhealthy",
            "services": services,
        }

        return Response(
            response_data,
            status=status.HTTP_200_OK
            if is_healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
