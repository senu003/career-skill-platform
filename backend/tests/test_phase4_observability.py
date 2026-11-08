import pytest
import logging
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.observability import (
    is_valid_request_id,
    resolve_request_id,
    mask_sensitive_data,
    SafeLogFilter,
    StructuredLogFormatter,
)
from app.services.readiness_service import (
    check_database,
    check_question_bank,
    check_storage,
    check_redis,
    check_ai_provider,
    perform_readiness_check,
)
from app.services.storage_service import LocalStorageBackend

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clean_app_overrides():
    yield
    app.dependency_overrides.clear()


# ===========================================================================
# 1. REQUEST ID VALIDATION, BOUNDING & TRACING
# ===========================================================================

def test_request_id_validation_logic():
    # Valid IDs
    assert is_valid_request_id("req_12345")
    assert is_valid_request_id("trace-id-abc.123_456")
    assert is_valid_request_id("a" * 128)

    # Invalid / unbounded IDs
    assert not is_valid_request_id("")
    assert not is_valid_request_id(None)
    assert not is_valid_request_id("a" * 129)  # Exceeds bounded limit
    assert not is_valid_request_id("req with spaces")
    assert not is_valid_request_id("<script>alert(1)</script>")
    assert not is_valid_request_id("req;drop table users;")


def test_resolve_request_id():
    # Valid incoming is preserved
    valid_id = "client-trace-12345"
    assert resolve_request_id(valid_id) == valid_id

    # Unbounded incoming (> 128 chars) is rejected and replaced with safe generated ID
    unbounded = "x" * 150
    generated = resolve_request_id(unbounded)
    assert generated != unbounded
    assert generated.startswith("req_")
    assert len(generated) < 60

    # Malicious incoming is rejected
    malicious = "bad/id;with$chars"
    generated2 = resolve_request_id(malicious)
    assert generated2 != malicious
    assert generated2.startswith("req_")


def test_response_includes_request_id_header():
    # 1. Auto-generated request ID when client sends none
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    auto_id = resp.headers["x-request-id"]
    assert auto_id.startswith("req_")

    # 2. Accepted bounded client request ID
    custom_id = "my-custom-trace-id-987"
    resp2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers.get("x-request-id") == custom_id

    # 3. Overly long request ID is sanitized
    long_id = "malicious_overflow_" + ("x" * 200)
    resp3 = client.get("/health", headers={"X-Request-ID": long_id})
    assert resp3.status_code == 200
    returned_id = resp3.headers.get("x-request-id")
    assert returned_id != long_id
    assert returned_id.startswith("req_")


# ===========================================================================
# 2. SAFE LOGGING & SANITIZATION
# ===========================================================================

def test_mask_sensitive_data():
    raw_log = 'User login failed with password="SuperSecretPassword123!" and token=Bearer eyJhbGciOiJIUzI1Ni...'
    masked = mask_sensitive_data(raw_log)
    assert "SuperSecretPassword123!" not in masked
    assert "[REDACTED]" in masked

    # Presigned URL signature masking
    s3_log = 'Generated URL https://s3.amazonaws.com/bucket/key.pdf?X-Amz-Signature=abcd1234ef5678&AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE'
    masked_s3 = mask_sensitive_data(s3_log)
    assert "X-Amz-Signature=[REDACTED]" in masked_s3

    # API key masking
    api_log = 'Configured with api_key="AIzaSyA_example_secret_key_123"'
    masked_api = mask_sensitive_data(api_log)
    assert "AIzaSyA_example_secret_key_123" not in masked_api
    assert "[REDACTED]" in masked_api


def test_safe_log_filter_injects_request_id():
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg='User authenticated with token="secret_jwt_token"',
        args=(),
        exc_info=None,
    )
    safe_filter = SafeLogFilter()
    result = safe_filter.filter(record)

    assert result is True
    assert hasattr(record, "request_id")
    assert "secret_jwt_token" not in record.msg
    assert "[REDACTED]" in record.msg


# ===========================================================================
# 3. CONSISTENT SAFE ERROR RESPONSES
# ===========================================================================

def test_error_response_structure_on_404():
    resp = client.get("/non_existent_route_404")
    assert resp.status_code == 404
    assert "x-request-id" in resp.headers

    data = resp.json()
    assert data["error_code"] == "NOT_FOUND"
    assert "request_id" in data
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["request_id"] == resp.headers["x-request-id"]


def test_error_response_structure_on_422_validation():
    # POST to /requirements/analyze with invalid payload body
    resp = client.post("/requirements/analyze", json={"invalid_field": 123})
    assert resp.status_code == 422
    assert "x-request-id" in resp.headers

    data = resp.json()
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "request_id" in data
    assert "detail" in data
    assert data["request_id"] == resp.headers["x-request-id"]


def test_500_error_conceals_internal_secrets_from_response():
    # Trigger unhandled exception containing sensitive database credentials
    with patch("sqlalchemy.orm.Query.first", side_effect=RuntimeError("psql: FATAL: password authentication failed for user 'postgres'")):
        resp = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code == 500
        data = resp.json()

        # The HTTP client must NEVER see the internal stack trace or raw DB credentials
        assert "FATAL" not in data["detail"]
        assert "postgres" not in data["detail"]
        assert data["detail"] == "Internal server error"
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "request_id" in data
        assert resp.headers.get("x-request-id") == data["request_id"]
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ===========================================================================
# 4. LIVENESS & READINESS CHECKS
# ===========================================================================

def test_liveness_endpoint_compatibility():
    # /health must remain backward compatible, returning 200 with status ok
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_readiness_endpoint_success():
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)  # Depends on local DB state
    data = resp.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
    assert "question_bank" in data["checks"]
    assert "storage" in data["checks"]
    assert "redis" in data["checks"]
    assert "ai_provider" in data["checks"]
    assert "request_id" in data
    assert resp.headers.get("x-request-id") == data["request_id"]


def test_readiness_controlled_db_failure():
    # Simulate DB connection failure
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = ConnectionRefusedError("PostgreSQL server down")

    code, data = perform_readiness_check(target_engine=mock_engine)
    assert code == 503
    assert data["status"] == "unhealthy"
    assert data["checks"]["database"]["status"] == "unhealthy"
    assert "failed" in data["checks"]["database"]["error"].lower()


def test_readiness_controlled_question_bank_failure():
    # Simulate empty question bank
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.count.return_value = 0
    mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

    code, data = perform_readiness_check(session_factory=mock_factory)
    assert code == 503
    assert data["status"] == "unhealthy"
    assert data["checks"]["question_bank"]["status"] == "unhealthy"
    assert data["checks"]["question_bank"]["total_active_questions"] == 0


def test_readiness_controlled_storage_failure():
    # Simulate storage failure (unwritable path)
    mock_storage = MagicMock(spec=LocalStorageBackend)
    mock_storage.base_dir = "/non_existent_unwritable_directory/uploads"

    with patch("os.makedirs", side_effect=PermissionError("Permission denied")):
        code, data = perform_readiness_check(storage_backend=mock_storage)
        assert code == 503
        assert data["status"] == "unhealthy"
        assert data["checks"]["storage"]["status"] == "unhealthy"


def test_readiness_redis_graceful_degradation():
    # When Redis is configured but unreachable:
    # App MUST report 'degraded' but return HTTP 200 (not 503), because rate limiting falls back to memory.
    with patch("redis.from_url") as mock_redis:
        mock_redis.return_value.ping.side_effect = TimeoutError("Redis connection timed out")

        # Isolated check
        redis_check = check_redis(redis_url="redis://localhost:6379/0", timeout_seconds=0.1)
        assert redis_check["status"] == "degraded"
        assert "fallback" in redis_check["message"]

        # Full readiness check: DB and QB healthy, Redis degraded -> HTTP 200 degraded
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 150
        mock_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_session), __exit__=MagicMock()))

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value.execute.return_value = None

        code, data = perform_readiness_check(
            target_engine=mock_engine,
            session_factory=mock_factory,
            redis_url="redis://localhost:6379/0"
        )
        assert code == 200
        assert data["status"] == "degraded"
        assert data["checks"]["redis"]["status"] == "degraded"


def test_readiness_avoids_live_ai_calls():
    # Verify check_ai_provider inspects config without calling google.genai or groq APIs
    ai_check = check_ai_provider()
    assert "live_probe" in ai_check
    assert ai_check["live_probe"] is False
    assert ai_check["status"] in ("ok", "unhealthy")



def test_simulated_ai_provider_failure_returns_safe_502():
    from app.rate_limiter import limiter
    limiter_was_enabled = getattr(limiter, "enabled", True)
    limiter.enabled = False
    try:
        with patch.dict("os.environ", {"SIMULATE_AI_FAILURE": "1"}):
            from app.auth_deps import get_current_user
            from app.models import User
            mock_user = User(id=1, email="test@test.com", is_active=True)
            app.dependency_overrides[get_current_user] = lambda: mock_user

            mock_cv_data = {
                "text": "Experienced Python Engineer with FastAPI and Docker.",
                "filename": "test_resume.pdf",
                "file_path": "uploads/test_resume.pdf",
            }
            with patch("app.routers.cv.process_cv", return_value=mock_cv_data):
                resp = client.post(
                    "/cv/analyze",
                    files={"file": ("test_resume.pdf", b"%PDF-1.4 dummy", "application/pdf")},
                    data={"requirements": '[{"skill": "Python", "level": "intermediate", "importance": "required"}]'},
                    headers={"X-Request-ID": "test-trace-sim-502"},
                )
                assert resp.status_code == 502
                data = resp.json()
                assert data["error_code"] == "AI_PROVIDER_ERROR"
                assert data["detail"] == "The AI analysis service is temporarily unavailable. Please try again in a few moments."
                assert data["request_id"] == "test-trace-sim-502"
                assert resp.headers.get("x-request-id") == "test-trace-sim-502"
                assert "Simulated" not in data["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        limiter.enabled = limiter_was_enabled


def test_403_forbidden_returns_consistent_error():
    from app.auth_deps import get_current_user_required
    from app.models import User, CV

    mock_user_b = User(id=999, email="other_user@test.com", is_active=True)
    app.dependency_overrides[get_current_user_required] = lambda: mock_user_b
    try:
        mock_cv = MagicMock(spec=CV)
        mock_cv.id = 123
        mock_cv.user_id = 100  # belongs to user 100, not 999!

        with patch("sqlalchemy.orm.Session.query") as mock_query:
            mock_filter = MagicMock()
            mock_filter.first.return_value = mock_cv
            mock_query.return_value.filter.return_value = mock_filter

            resp = client.get("/cv/123/download")
            assert resp.status_code == 403
            data = resp.json()
            assert data["error_code"] == "FORBIDDEN"
            assert "request_id" in data
            assert resp.headers.get("x-request-id") == data["request_id"]
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)
