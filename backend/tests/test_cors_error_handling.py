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
    # It might return a 400 Bad Request for preflight, or just return 200 without headers.
    assert response.headers.get("access-control-allow-origin") != "http://untrusted.com"


def test_global_exception_handler():
    # Mocking a function in users router to raise a generic exception
    with patch("app.routers.users.get_me", side_effect=Exception("Top secret traceback details")):
        # Overriding dependency for current_user is tricky, let's mock the db session instead for an unauthenticated route
        # Actually /cv/latest needs auth. We can mock a service function called in an unauthenticated way or just the router function.
        pass

    # A better approach: we can just use the login endpoint and mock the db call
    with patch("sqlalchemy.orm.Query.first", side_effect=ValueError("Database secret leak")):
        response = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"}
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}


def test_sqlalchemy_exception_handler():
    # Mock an SQLAlchemy error
    with patch("sqlalchemy.orm.Query.first", side_effect=SQLAlchemyError("Raw SQL syntax error")):
        response = client.post(
            "/login",
            data={"username": "test@test.com", "password": "password"}
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}


def test_intentional_http_exception_preserved():
    # 404 error
    response = client.get("/cv/sessions/999999")
    assert response.status_code == 401 # Because it's unauthorized first!

    # Let's mock a user token to get 404
    from app.auth_deps import get_current_user_required
    from app.models import User
    
    mock_user = User(id=1, email="test@test.com")
    app.dependency_overrides[get_current_user_required] = lambda: mock_user
    
    response = client.get("/cv/sessions/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis session not found."}
    app.dependency_overrides.pop(get_current_user_required, None)
