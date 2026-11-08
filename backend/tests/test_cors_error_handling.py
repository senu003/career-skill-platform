import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from unittest.mock import patch

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_cors_trusted_origin():
    response = client.options(
        "/cv/latest",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_untrusted_origin():
    response = client.options(
        "/cv/latest",
        headers={
            "Origin": "http://untrusted.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    # If the origin is not allowed, CORSMiddleware does not return it in the headers.
    assert response.headers.get("access-control-allow-origin") != "http://untrusted.com"


def test_global_exception_handler():
    # Login endpoint with simulated unexpected error
    with patch("sqlalchemy.orm.Query.first", side_effect=ValueError("Database secret leak")):
        response = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"}
        )
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert "request_id" in data
        assert response.headers.get("x-request-id") == data["request_id"]


def test_sqlalchemy_exception_handler():
    # Mock an SQLAlchemy error
    with patch("sqlalchemy.orm.Query.first", side_effect=SQLAlchemyError("Raw SQL syntax error")):
        response = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"}
        )
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Internal server error"
        assert data["error_code"] == "DATABASE_ERROR"
        assert "request_id" in data
        assert response.headers.get("x-request-id") == data["request_id"]


def test_intentional_http_exception_preserved():
    # 404 error
    response = client.get("/cv/sessions/999999")
    assert response.status_code == 401 # Because it's unauthorized first!

    # Mock user token to test 404
    from app.auth_deps import get_current_user_required
    from app.models import User

    mock_user = User(id=1, email="test@test.com")
    app.dependency_overrides[get_current_user_required] = lambda: mock_user

    response = client.get("/cv/sessions/999999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Analysis session not found."
    assert "request_id" in data
    assert response.headers.get("x-request-id") == data["request_id"]
    app.dependency_overrides.pop(get_current_user_required, None)


def test_global_exception_handler_preserves_cors_headers():
    with patch("sqlalchemy.orm.Query.first", side_effect=RuntimeError("Unexpected unhandled error")):
        response = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 500
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        data = response.json()
        assert data["detail"] == "Internal server error"
        assert "request_id" in data
        assert response.headers.get("x-request-id") == data["request_id"]


def test_google_auth_invalid_token_returns_401_with_cors():
    response = client.post(
        "/auth/google",
        json={"credential": "invalid-dummy-credential"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "Invalid Google credentials" in response.json()["detail"]
    assert "request_id" in response.json()
    assert response.headers.get("x-request-id") == response.json()["request_id"]


def test_google_auth_successful_login_and_user_creation():
    mock_payload = {
        "sub": "google-uid-99999",
        "google_id": "google-uid-99999",
        "email": "verified_google_candidate@example.com",
        "name": "Verified Google Candidate",
        "picture": "https://example.com/avatar.jpg",
        "email_verified": True,
    }
    with patch("app.routers.auth.verify_google_token", return_value=mock_payload):
        response = client.post(
            "/auth/google",
            json={"credential": "mocked-valid-google-jwt-token"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "verified_google_candidate@example.com"
        assert data["user"]["name"] == "Verified Google Candidate"
        assert data["user"]["oauth_provider"] == "google"
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert response.headers.get("x-request-id") is not None
