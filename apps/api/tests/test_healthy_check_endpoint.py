from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from app.core.api.v1.views import HealthAPICheck


class HealthAPITest(APITestCase):
    def setUp(self):
        self.url = "/api/v1/health/"

    def test_health_check_success(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["services"]["database"], "healthy")
        self.assertEqual(response.data["services"]["cache"], "healthy")

    def test_health_check_database_down(self):
        mock_db = MagicMock()
        mock_db.is_usable.return_value = False

        with patch.object(HealthAPICheck, "db_connection", mock_db):
            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(response.data["status"], "unhealthy")
            self.assertEqual(response.data["services"]["database"], "unhealthy")
            self.assertEqual(response.data["services"]["cache"], "healthy")

    def test_health_check_cache_ping_down(self):
        mock_cache = MagicMock()
        mock_cache.ping.side_effect = Exception("Redis Timeout")

        with patch.object(HealthAPICheck, "cache_provider", mock_cache):
            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(response.data["status"], "unhealthy")
            self.assertEqual(response.data["services"]["cache"], "unhealthy")
            self.assertEqual(response.data["services"]["database"], "healthy")

    def test_health_check_cache_fallback_down(self):
        mock_cache = MagicMock(spec=["set", "get"])
        mock_cache.set.side_effect = Exception("Cache Write Error")

        with patch.object(HealthAPICheck, "cache_provider", mock_cache):
            response = self.client.get(self.url)

            self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
            self.assertEqual(response.data["status"], "unhealthy")
            self.assertEqual(response.data["services"]["cache"], "unhealthy")
            self.assertEqual(response.data["services"]["database"], "healthy")
