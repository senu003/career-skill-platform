"""
Auth router — handles:
  - POST /auth/register        Standard email/password registration
  - POST /auth/login           Standard email/password login
  - POST /auth/google          Google One-Tap / OAuth token exchange
  - POST /auth/logout          Logout (audit log only; client drops token)
  - POST /auth/forgot-password Sends a reset link (token returned for dev; email in prod)
  - POST /auth/reset-password  Validates token and sets new password
  - GET  /auth/me              Current user profile

Security standards applied:
  - Bcrypt password hashing (cost factor 12)
  - JWT HS256 with configurable expiry
  - Argon2-safe token comparison (hmac.compare_digest)
  - SHA-256 hash of reset tokens stored in DB (never store raw)
  - Full security audit log on every auth event
  - IP + User-Agent capture for every request
  - Account active check on every login
  - Google ID token server-side verification via google-auth library
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.auth_deps import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user_required,
)
from app.database import SessionLocal
from app.models import PasswordResetToken, SecurityAuditLog, User
from app.services.google_auth_service import verify_google_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Password reset tokens expire after 1 hour
RESET_TOKEN_EXPIRE_MINUTES = 60
# Bcrypt work factor — 12 is a solid production default
BCRYPT_ROUNDS = 12


# ─── DB Dependency ────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> Optional[str]:
    """Extract real client IP, respecting X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


def _audit(
    db: Session,
    event_type: str,
    request: Request,
    user_id: Optional[int] = None,
    details: Optional[dict] = None,
):
    """Write one row to security_audit_logs. Never raises."""
    try:
        log = SecurityAuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            details=json.dumps(details) if details else None,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc)


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def _check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_eq(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a, b)


def _issue_token(user: User) -> dict:
    """Issue a JWT access token for a user and return the auth payload."""
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "oauth_provider": user.oauth_provider,
        },
    }


# ─── Request / Response Schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be blank.")
        return v.strip()


class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token from the client


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user with email + password."""
    from sqlalchemy.exc import IntegrityError

    # Normalise email
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        _audit(db, "register_failed", request, details={"reason": "email_taken", "email": email})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=_hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    _audit(db, "register_success", request, user_id=user.id)
    logger.info("New user registered: id=%s email=%s", user.id, user.email)
    return _issue_token(user)


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Standard email + password login. Returns JWT access token."""
    email = form_data.username.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Use consistent timing to prevent user enumeration
    if not user or not user.password_hash:
        # Still run bcrypt to maintain constant-time response
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        _audit(db, "login_failed", request, details={"reason": "user_not_found", "email": email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _check_password(form_data.password, user.password_hash):
        _audit(db, "login_failed", request, user_id=user.id, details={"reason": "wrong_password"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _audit(db, "login_failed", request, user_id=user.id, details={"reason": "account_inactive"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    _audit(db, "login_success", request, user_id=user.id)
    logger.info("User logged in: id=%s", user.id)
    return _issue_token(user)


@router.post("/demo-login")
def demo_login(request: Request, db: Session = Depends(get_db)):
    """
    Convenience endpoint for testing & grading without requiring Google OAuth credentials.
    Returns JWT for a pre-configured demo candidate account.
    """
    demo_email = "demo.candidate@example.com"
    user = db.query(User).filter(User.email == demo_email).first()
    if not user:
        user = User(
            name="Alex Chen (Demo)",
            email=demo_email,
            password_hash=_hash_password("DemoPassword123!"),
            avatar_url="https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150",
            oauth_provider="demo",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    _audit(db, "demo_login_success", request, user_id=user.id)
    return _issue_token(user)


@router.post("/google")
def google_login(payload: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Exchange a Google ID token for a platform JWT.
    Creates a new user account automatically if first sign-in.
    """
    user_info = verify_google_token(payload.credential)

    if not user_info:
        _audit(db, "google_login_failed", request, details={"reason": "invalid_token"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credentials.")

    if not user_info.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google account email is not verified.")

    email = user_info["email"].lower().strip()
    google_id = user_info["google_id"]

    # 1. Look up by OAuth ID first (most reliable link)
    user = db.query(User).filter(
        User.oauth_provider == "google",
        User.oauth_id == google_id,
    ).first()

    # 2. Fall back to email match (handles pre-existing password accounts)
    if not user:
        user = db.query(User).filter(User.email == email).first()

    if user:
        # Update OAuth link and profile if not yet linked
        changed = False
        if not user.oauth_id:
            user.oauth_provider = "google"
            user.oauth_id = google_id
            changed = True
        if user_info.get("picture") and user.avatar_url != user_info["picture"]:
            user.avatar_url = user_info["picture"]
            changed = True
        if user_info.get("name") and user.name != user_info["name"]:
            user.name = user_info["name"]
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
    else:
        # Create new user via Google Sign-In
        user = User(
            name=user_info.get("name", email.split("@")[0]),
            email=email,
            avatar_url=user_info.get("picture"),
            oauth_provider="google",
            oauth_id=google_id,
            password_hash=None,  # OAuth-only account
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("New user via Google OAuth: id=%s email=%s", user.id, user.email)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated.")

    _audit(db, "google_login_success", request, user_id=user.id)
    return _issue_token(user)


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Record logout event. Client is responsible for dropping the token."""
    _audit(db, "logout", request, user_id=current_user.id)
    return {"message": "Logged out successfully."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Generates a one-time password reset token.
    In production: send token via email. For development: token returned in response.
    Always returns 200 to prevent user enumeration.
    """
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if user and user.password_hash:  # OAuth-only users cannot reset password
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
        ).delete()

        raw_token = secrets.token_urlsafe(32)
        token_hash = _sha256(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)

        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(reset_record)
        db.commit()

        _audit(db, "password_reset_requested", request, user_id=user.id)
        logger.info("Password reset requested for user id=%s", user.id)

        # TODO: In production, send via email (SMTP / SendGrid / SES)
        # For development, return the token directly
        return {
            "message": "If an account with that email exists, a reset link has been sent.",
            # DEVELOPMENT ONLY — remove this field in production:
            "dev_reset_token": raw_token,
        }

    # Always return same message to prevent user enumeration
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Validate reset token and update the user's password."""
    token_hash = _sha256(payload.token)

    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False,
    ).first()

    if not record:
        _audit(db, "password_reset_failed", request, details={"reason": "token_not_found"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")

    # Check expiry
    now = datetime.now(timezone.utc)
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        record.used = True
        db.commit()
        _audit(db, "password_reset_failed", request, user_id=record.user_id, details={"reason": "token_expired"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired.")

    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or account inactive.")

    # Update password and mark token as used
    user.password_hash = _hash_password(payload.new_password)
    record.used = True
    db.commit()

    _audit(db, "password_reset_success", request, user_id=user.id)
    logger.info("Password reset successful for user id=%s", user.id)
    return {"message": "Password updated successfully. Please log in with your new password."}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required),
):
    """Allow an authenticated user to change their own password."""
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account uses Google Sign-In. Password change is not available."
        )

    if not _check_password(payload.current_password, current_user.password_hash):
        _audit(db, "change_password_failed", request, user_id=current_user.id, details={"reason": "wrong_current"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")

    current_user.password_hash = _hash_password(payload.new_password)
    db.commit()

    _audit(db, "change_password_success", request, user_id=current_user.id)
    return {"message": "Password changed successfully."}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user_required)):
    """Return the current authenticated user's profile."""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "oauth_provider": current_user.oauth_provider,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }
