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
    revoke_token,
    is_token_revoked,
    KNOWN_INSECURE_SECRETS,
)
from app.services.requirement_service import _get_ssl_verify
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
        self.db.execute(text("DELETE FROM revoked_tokens WHERE user_id IN (SELECT id FROM users WHERE email = 'p2_test@example.com')"))
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
        self.db.execute(text("DELETE FROM revoked_tokens WHERE user_id = :uid"), {"uid": self.user_id})
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


    # ──────────────────────────────────────────────────────────────────────────
    # Fix 3: Inactive-Account Rejection on Protected Endpoints
    # ──────────────────────────────────────────────────────────────────────────

    def test_inactive_account_token_rejected_on_protected_endpoints(self):
        """Tokens issued before deactivation must be rejected on protected endpoints with 401."""
        # 1. Login to receive valid token
        login_res = self.client.post("/login", data={"username": "p2_test@example.com", "password": "ValidPassword123!"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]

        # 2. Access protected endpoint while active
        me_res = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["email"], "p2_test@example.com")

        # 3. Deactivate user in database
        self.db.execute(text("UPDATE users SET is_active = FALSE WHERE id = :uid"), {"uid": self.user_id})
        self.db.commit()

        # 4. Token must be rejected when attempting to access /auth/me
        me_res_inactive = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res_inactive.status_code, 401)
        self.assertIn("Account is deactivated", me_res_inactive.json().get("detail", ""))

        # 5. Token must be rejected on other protected endpoints (e.g. /cv/latest)
        cv_res_inactive = self.client.get("/cv/latest", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(cv_res_inactive.status_code, 401)
        self.assertIn("Account is deactivated", cv_res_inactive.json().get("detail", ""))

        # 6. Subsequent login must be forbidden with 403
        login_res_inactive = self.client.post("/login", data={"username": "p2_test@example.com", "password": "ValidPassword123!"})
        self.assertEqual(login_res_inactive.status_code, 403)
        self.assertIn("Account is deactivated", login_res_inactive.json().get("detail", ""))

    # ──────────────────────────────────────────────────────────────────────────
    # Fix 4: Groq TLS Certificate Verification
    # ──────────────────────────────────────────────────────────────────────────

    def test_groq_tls_verification_defaults_to_true(self):
        """By default, _get_ssl_verify() must return True to enforce TLS certificate verification."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove custom CA overrides if set
            for k in ("GROQ_SSL_CERT", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
                os.environ.pop(k, None)
            verify = _get_ssl_verify()
            self.assertIs(verify, True)

    def test_groq_tls_verification_supports_custom_ca(self):
        """When custom CA bundle is specified in env and exists, _get_ssl_verify() returns that path."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as ca_file:
            ca_file.write(b"-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")
            ca_path = ca_file.name

        try:
            with patch.dict(os.environ, {"GROQ_SSL_CERT": ca_path}, clear=False):
                verify = _get_ssl_verify()
                self.assertEqual(verify, ca_path)
        finally:
            if os.path.exists(ca_path):
                os.remove(ca_path)

    def test_requirement_service_contains_no_disabled_tls_verification(self):
        """Verify requirement_service.py source code has zero occurrences of verify=False."""
        service_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "services", "requirement_service.py"))
        with open(service_path, "r", encoding="utf-8") as f:
            service_code = f.read()

        self.assertNotIn(
            "verify=False",
            service_code,
            "requirement_service.py must not disable TLS verification (verify=False is prohibited)."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Fix 5: Server-Side Token Revocation & Store Fallback
    # ──────────────────────────────────────────────────────────────────────────

    def test_logout_revokes_token_and_rejects_subsequent_use(self):
        """POST /auth/logout must revoke the bearer token and reject subsequent reuse with 401."""
        # 1. Login
        login_res = self.client.post("/login", data={"username": "p2_test@example.com", "password": "ValidPassword123!"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["access_token"]

        # 2. Call protected endpoint before logout
        res_before = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_before.status_code, 200)

        # 3. Call logout
        logout_res = self.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)
        self.assertEqual(logout_res.json()["message"], "Logged out successfully.")

        # 4. Attempt to reuse the revoked token
        res_after = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_after.status_code, 401)
        self.assertIn("Token has been revoked", res_after.json().get("detail", ""))

        # 5. Verify database revoked_tokens table has record
        revoked_count = self.db.execute(
            text("SELECT COUNT(*) FROM revoked_tokens WHERE user_id = :uid"),
            {"uid": self.user_id}
        ).scalar()
        self.assertGreaterEqual(revoked_count, 1)

    def test_token_revocation_store_resilience_when_redis_unavailable(self):
        """Revocation must fall back to in-memory + database when Redis is offline or raises error."""
        token = create_access_token({"sub": str(self.user_id)})

        # Simulate Redis unavailability
        with patch("app.auth_deps.get_redis_client", return_value=None):
            # Revocation must still succeed
            revoked = revoke_token(token, db=self.db, user_id=self.user_id)
            self.assertTrue(revoked)

            # Verification must report token as revoked
            is_rev = is_token_revoked(token, db=self.db)
            self.assertTrue(is_rev)

        # Calling protected endpoint with this token must be rejected
        res = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Token has been revoked", res.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
