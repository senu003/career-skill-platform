import os
import sys
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.auth_deps import (
    validate_jwt_secret,
    create_access_token,
    get_current_user,
    KNOWN_INSECURE_SECRETS,
)
from app.services.email_service import (
    is_production,
    is_secure_email_available,
    is_password_reset_enabled,
)


class TestPhase2SecurityFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        # Clean up test records
        self.db.execute(text("DELETE FROM password_reset_tokens WHERE user_id IN (SELECT id FROM users WHERE email = 'p2_test@example.com')"))
        self.db.execute(text("DELETE FROM users WHERE email = 'p2_test@example.com'"))
        self.db.commit()

        # Register test user
        self.client.post("/auth/register", json={
            "name": "Phase2 User",
            "email": "p2_test@example.com",
            "password": "ValidPassword123!",
        })
        self.user_id = self.db.execute(text("SELECT id FROM users WHERE email = 'p2_test@example.com'")).scalar()

    def tearDown(self):
        self.db.execute(text("DELETE FROM password_reset_tokens WHERE user_id = :uid"), {"uid": self.user_id})
        self.db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": self.user_id})
        self.db.commit()
        self.db.close()

    # ──────────────────────────────────────────────────────────────────────────
    # Fix 1: Password Reset Token Non-Disclosure & Production Email Availability
    # ──────────────────────────────────────────────────────────────────────────

    def test_forgot_password_never_returns_raw_token_in_response(self):
        """Verify that POST /auth/forgot-password never returns dev_reset_token or raw token in JSON."""
        res = self.client.post("/auth/forgot-password", json={"email": "p2_test@example.com"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("message", data)
        self.assertNotIn("dev_reset_token", data)
        self.assertNotIn("token", data)
        self.assertNotIn("raw_token", data)

    def test_forgot_password_uniform_response_for_nonexistent_user(self):
        """Prevent user enumeration: returns identical 200 message with no token for unregistered email."""
        res = self.client.post("/auth/forgot-password", json={"email": "nonexistent_p2@example.com"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["message"], "If an account with that email exists, a reset link has been sent.")
        self.assertNotIn("dev_reset_token", data)

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SMTP_HOST": "", "SECURE_EMAIL_DELIVERY_ENABLED": "0"}, clear=False)
    def test_forgot_password_disabled_in_production_when_email_unavailable(self):
        """In production without secure email, forgot-password must fail closed (503 Service Unavailable)."""
        res = self.client.post("/auth/forgot-password", json={"email": "p2_test@example.com"})
        self.assertEqual(res.status_code, 503)
        self.assertIn("secure email delivery is not configured", res.json()["detail"])

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SMTP_HOST": "", "SECURE_EMAIL_DELIVERY_ENABLED": "0"}, clear=False)
    def test_reset_password_disabled_in_production_when_email_unavailable(self):
        """In production without secure email, reset-password must fail closed (503 Service Unavailable)."""
        res = self.client.post("/auth/reset-password", json={"token": "some-token", "new_password": "NewValidPass123!"})
        self.assertEqual(res.status_code, 503)
        self.assertIn("secure email delivery is not configured", res.json()["detail"])

    @patch.dict(os.environ, {"ENVIRONMENT": "production", "SMTP_HOST": "", "SECURE_EMAIL_DELIVERY_ENABLED": "0"}, clear=False)
    def test_password_reset_status_disabled_in_production_without_email(self):
        """GET /auth/password-reset/status reports disabled in production when email is unavailable."""
        res = self.client.get("/auth/password-reset/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["enabled"])
        self.assertFalse(data["email_delivery_available"])
        self.assertEqual(data["environment"], "production")

    @patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "mailer",
        "SMTP_PASSWORD": "secretpassword",
        "SECURE_EMAIL_DELIVERY_ENABLED": "1",
    }, clear=False)
    @patch("app.routers.auth.send_password_reset_email")
    def test_forgot_password_in_production_with_email_delivers_out_of_band(self, mock_send_email):
        """In production with secure email, token is dispatched out-of-band and never exposed in JSON."""
        mock_send_email.return_value = True

        res = self.client.post("/auth/forgot-password", json={"email": "p2_test@example.com"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("dev_reset_token", data)
        self.assertNotIn("token", data)

        # Confirm send_password_reset_email was invoked with out-of-band raw token
        self.assertTrue(mock_send_email.called)
        call_args = mock_send_email.call_args[0]
        self.assertEqual(call_args[0], "p2_test@example.com")
        self.assertGreaterEqual(len(call_args[1]), 32)

    # ──────────────────────────────────────────────────────────────────────────
    # Fix 2: JWT Secret Enforcement & Removal of Fallbacks
    # ──────────────────────────────────────────────────────────────────────────

    def test_jwt_secret_validation_rejects_missing_or_empty(self):
        """Reject missing, None, empty, or whitespace secrets in all environments."""
        with self.assertRaises(RuntimeError) as ctx:
            validate_jwt_secret(None, environment="development")
        self.assertIn("missing or empty", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            validate_jwt_secret("", environment="production")
        self.assertIn("missing or empty", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            validate_jwt_secret("   ", environment="production")
        self.assertIn("missing or empty", str(ctx.exception))

    def test_jwt_secret_validation_production_rejects_weak_secrets(self):
        """In production, reject secrets shorter than 32 characters (256 bits for HS256)."""
        weak_secrets = [
            "short",
            "12345678901234567890",
            "under_32_characters_secret_key!",
        ]
        for weak in weak_secrets:
            with self.assertRaises(RuntimeError) as ctx:
                validate_jwt_secret(weak, environment="production")
            self.assertIn("too weak", str(ctx.exception))

    def test_jwt_secret_validation_production_rejects_low_entropy(self):
        """In production, reject secrets with poor character diversity / entropy."""
        low_entropy_secrets = [
            "a" * 32,
            "12312312312312312312312312312312",
        ]
        for s in low_entropy_secrets:
            with self.assertRaises(RuntimeError) as ctx:
                validate_jwt_secret(s, environment="production")
            self.assertIn("insufficient entropy", str(ctx.exception))

    def test_jwt_secret_validation_production_rejects_known_defaults(self):
        """In production, reject checked-in default, example, or development keys."""
        known_defaults = [
            "career-skill-platform-super-secret-jwt-key-256bits-development-only",
            "ci-test-secret-key-256bits-min-length-required-for-hs256",
            "replace-with-a-secure-random-secret-key-at-least-32-chars",
            "your-secret-key-here-must-be-long-enough-for-hs256",
            "this-is-a-development-only-secret-key-for-testing",
            "changeme-super-long-insecure-secret-key-12345",
        ]
        for default_key in known_defaults:
            with self.assertRaises(RuntimeError) as ctx:
                validate_jwt_secret(default_key, environment="production")
            self.assertIn("known default", str(ctx.exception))

    def test_jwt_secret_validation_production_accepts_strong_secret(self):
        """In production, accept unique, high-entropy 32+ character secrets."""
        strong_key = "k9#mP$2vL@8xQ!5zR^1wT&4yN*7bV~0dF"
        validated = validate_jwt_secret(strong_key, environment="production")
        self.assertEqual(validated, strong_key)

    def test_docker_compose_has_no_fallback_jwt_secret(self):
        """Verify that docker-compose.yml does not supply a fallback JWT secret and sets production environment."""
        compose_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml"))
        self.assertTrue(os.path.exists(compose_path))

        with open(compose_path, "r", encoding="utf-8") as f:
            compose_content = f.read()

        # Must not contain fallback default secret syntax for JWT_SECRET
        self.assertNotIn(
            "career-skill-platform-super-secret-jwt-key-256bits-development-only",
            compose_content,
            "docker-compose.yml must not contain the known default JWT secret fallback."
        )
        self.assertIn("JWT_SECRET=${JWT_SECRET}", compose_content)
        self.assertIn("ENVIRONMENT=${ENVIRONMENT:-production}", compose_content)


if __name__ == "__main__":
    unittest.main()
