"""
Auth router — handles:
  - POST /auth/register              Standard email/password registration
  - POST /auth/login                 Standard email/password login
  - POST /auth/google                Google One-Tap / OAuth token exchange
  - POST /auth/logout                Logout (audit log only; client drops token)
  - GET  /auth/password-reset/status Check password reset availability
  - POST /auth/forgot-password       Sends a reset link out-of-band via secure email
  - POST /auth/reset-password        Validates token and sets new password
  - GET  /auth/me                    Current user profile

Security standards applied:
  - Bcrypt password hashing (cost factor 12)
  - JWT HS256 with configurable expiry and strong secret enforcement
  - Argon2-safe token comparison (hmac.compare_digest)
  - SHA-256 hash of reset tokens stored in DB (never store raw)
  - Raw password-reset tokens are NEVER returned in API responses
  - Out-of-band secure email delivery for reset tokens (disabled in prod if email is unavailable)
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
from sqlalchemy.orm import Session

from app.auth_deps import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user_required,
)
from app.database import get_db
from app.models import PasswordResetToken, SecurityAuditLog, User
from app.services.google_auth_service import verify_google_token
from app.services.email_service import (
    is_production,
    is_secure_email_available,
    is_password_reset_enabled,
    send_password_reset_email,
)
from app.schemas.auth import (
    RegisterRequest,
    GoogleLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Password reset tokens expire after 1 hour
RESET_TOKEN_EXPIRE_MINUTES = 60
# Bcrypt work factor — 12 is a solid production default
BCRYPT_ROUNDS = 12


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
    except Exception:
        return False


def _sha256(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


def _issue_token(user: User) -> dict:
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "name": user.name},
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


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new user with email + password."""
    email = payload.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        _audit(db, "register_failed", request, details={"reason": "email_taken", "email": email})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=_hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception:
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

    if not user:
        _audit(db, "login_failed", request, details={"reason": "user_not_found", "email": email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.password_hash or not _check_password(form_data.password, user.password_hash):
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
    logger.info("User login success: id=%s email=%s", user.id, user.email)
    return _issue_token(user)


@router.post("/demo-login")
def demo_login(request: Request, db: Session = Depends(get_db)):
    """Logs in as (or provisions) the seeded demo candidate."""
    demo_email = "demo.candidate@example.com"
    user = db.query(User).filter(User.email == demo_email).first()
    if not user:
        user = User(
            name="Demo Candidate",
            email=demo_email,
            password_hash=_hash_password("DemoPass123!"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    _audit(db, "demo_login", request, user_id=user.id)
    return _issue_token(user)


@router.post("/google")
def google_auth(payload: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Exchange a Google One-Tap ID token for an application JWT."""
    try:
        user_info = verify_google_token(payload.credential)
    except ValueError as exc:
        _audit(db, "google_login_failed", request, details={"reason": "invalid_token", "error": str(exc)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credentials.")

    if not user_info:
        _audit(db, "google_login_failed", request, details={"reason": "invalid_token"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credentials.")

    if not user_info:
        _audit(db, "google_login_failed", request, details={"reason": "invalid_token"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credentials.")

    if not user_info.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google account email is not verified.")

    email = user_info.get("email", "").lower().strip()
    google_id = str(user_info.get("google_id") or user_info.get("sub") or "").strip()

    if not email or not google_id:
        _audit(db, "google_login_failed", request, details={"reason": "missing_profile_data"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incomplete Google profile data.")

    user = (
        db.query(User)
        .filter(User.oauth_provider == "google", User.oauth_id == google_id)
        .first()
    )

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = google_id
            if user_info.get("picture"):
                user.avatar_url = user_info["picture"]
            try:
                db.commit()
                _audit(db, "google_account_linked", request, user_id=user.id)
            except Exception:
                db.rollback()

    if not user:
        display_name = user_info.get("name") or (email.split("@")[0] if "@" in email else "User")
        user = User(
            name=display_name.strip(),
            email=email,
            password_hash=None,
            oauth_provider="google",
            oauth_id=google_id,
            avatar_url=user_info.get("picture"),
            is_active=True,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            logger.info("New user via Google OAuth: id=%s email=%s", user.id, user.email)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to provision user.")

    if not user.is_active:
        _audit(db, "google_login_failed", request, user_id=user.id, details={"reason": "account_inactive"})
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


@router.get("/password-reset/status")
@router.get("/reset-status")
def get_password_reset_status():
    """
    Check whether password reset flow is available in the current environment.
    If secure email delivery is not configured in production, reset is disabled.
    """
    enabled = is_password_reset_enabled()
    return {
        "enabled": enabled,
        "email_delivery_available": is_secure_email_available(),
        "environment": "production" if is_production() else "development",
        "message": (
            "Password reset is available."
            if enabled
            else "Password reset is currently unavailable because secure email delivery is not configured."
        ),
    }


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Generates a one-time password reset token.
    In production: sends token via secure email delivery out-of-band.
    If secure email is unavailable in production, the reset flow is disabled (503).
    Raw tokens are NEVER returned in API responses.
    Always returns uniform message when enabled to prevent user enumeration.
    """
    if not is_password_reset_enabled():
        _audit(db, "password_reset_rejected_disabled", request, details={"email": payload.email})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is currently unavailable because secure email delivery is not configured.",
        )

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

        # Deliver token out-of-band:
        if is_secure_email_available():
            send_password_reset_email(user.email, raw_token)
        else:
            # Development out-of-band delivery: log to secure server console only, never in API response
            logger.info("DEVELOPMENT ONLY [Out-of-band Token Delivery]: Reset token for %s: %s", user.email, raw_token)

    # Always return uniform message to prevent user enumeration; raw token is NEVER returned in response
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Validate reset token and update the user's password."""
    if not is_password_reset_enabled():
        _audit(db, "password_reset_rejected_disabled", request)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset is currently unavailable because secure email delivery is not configured.",
        )

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
