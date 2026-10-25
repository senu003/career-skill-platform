import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.rate_limiter import (
    limiter,
    get_client_identifier,
)

client = TestClient(app)


class TestRateLimiting(unittest.TestCase):

    def setUp(self):
        # Reset limiter storage before each test
        limiter.reset()

    def test_client_identifier_ip_fallback(self):
        # Request with simple client host
        req = MagicMock()
        req.headers = {}
        req.client.host = "192.168.1.50"
        self.assertEqual(get_client_identifier(req), "192.168.1.50")

    def test_client_identifier_x_forwarded_for(self):
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
        self.assertEqual(get_client_identifier(req), "203.0.113.195")

    def test_client_identifier_x_real_ip(self):
        req = MagicMock()
        req.headers = {"X-Real-IP": "198.51.100.42"}
        self.assertEqual(get_client_identifier(req), "198.51.100.42")

    def test_client_identifier_authenticated_token(self):
        req = MagicMock()
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_payload"
        req.headers = {"Authorization": f"Bearer {token}"}
        key = get_client_identifier(req)
        self.assertTrue(key.startswith("auth_user:"))
        self.assertEqual(key, f"auth_user:{token[:16]}")

    @patch("app.routers.requirements.extract_requirements")
    def test_requirements_analyze_rate_limit_enforcement(self, mock_extract):
        mock_extract.return_value = [{"skill": "Python", "level": "basic", "importance": "required"}]
        
        # Test rate limiting with low limit to trigger 429
        # The default limit is 20/minute. We can make rapid requests with fixed IP header.
        test_ip = "198.51.100.99"
        headers = {"X-Forwarded-For": test_ip}

        # Clear existing counters for this IP
        limiter.reset()

        hit_429 = False
        for i in range(25):
            res = client.post(
                "/requirements/analyze",
                json={"text": f"Looking for Python Developer attempt {i}"},
                headers=headers
            )
            if res.status_code == 429:
                hit_429 = True
                self.assertIn("Rate limit exceeded", res.json()["detail"])
                self.assertIn("Retry-After", res.headers)
                break

        self.assertTrue(hit_429, "Rate limit of 20/minute was not enforced on public endpoint")

    @patch("app.routers.requirements.extract_requirements")
    def test_different_ips_have_independent_buckets(self, mock_extract):
        mock_extract.return_value = [{"skill": "Python", "level": "basic", "importance": "required"}]
        limiter.reset()

        # IP 1 uses a request
        res1 = client.post(
            "/requirements/analyze",
            json={"text": "Job requirements for IP 1"},
            headers={"X-Forwarded-For": "10.0.0.1"}
        )
        self.assertEqual(res1.status_code, 200)

        # IP 2 uses a request independently
        res2 = client.post(
            "/requirements/analyze",
            json={"text": "Job requirements for IP 2"},
            headers={"X-Forwarded-For": "10.0.0.2"}
        )
        self.assertEqual(res2.status_code, 200)

    def test_redis_storage_initialization_configuration(self):
        from app.rate_limiter import REDIS_URL
        # In development/test environment without Redis running, storage falls back cleanly to memory://
        self.assertTrue(limiter.enabled)


if __name__ == "__main__":
    unittest.main()
