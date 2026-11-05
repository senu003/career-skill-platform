import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from app.database import SessionLocal, get_db
from app.models import User

load_dotenv()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

KNOWN_INSECURE_SECRETS = {
    "career-skill-platform-super-secret-jwt-key-256bits-development-only",
    "ci-test-secret-key-256bits-min-length-required-for-hs256",
    "replace-with-a-secure-random-secret-key-at-least-32-chars",
    "your-secret-key-here",
    "your_secret_key_here",
    "your-jwt-secret-here",
    "your_jwt_secret_here",
    "secret",
    "secretkey",
    "jwt_secret",
    "jwt-secret",
    "supersecret",
    "changeme",
    "defaultsecret",
    "development-only",
    "12345678901234567890123456789012",
}

INSECURE_SUBSTRINGS = (
    "development-only",
    "changeme",
    "example",
    "placeholder",
    "your-secret",
    "your_secret",
    "replace-with",
    "default-secret",
)


_UNSET = object()


def validate_jwt_secret(secret: object = _UNSET, environment: Optional[str] = None) -> str:
    """
    Validate JWT secret for cryptographic soundness and policy enforcement.
    In production: strictly rejects missing, weak (<32 chars, low entropy), or known default secrets.
    """
    if secret is _UNSET:
        secret = os.getenv("JWT_SECRET")
    if environment is None:
        environment = (
            os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or os.getenv("NODE_ENV")
            or "development"
        )

    is_prod = str(environment).strip().lower() in ("production", "prod")

    if secret is None or not str(secret).strip():
        raise RuntimeError("JWT_SECRET environment variable is missing or empty. A secure secret is required.")

    cleaned_secret = str(secret).strip()

    if is_prod:
        # Minimum key length for HS256 (RFC 7518 section 3.2: 256 bits = 32 bytes)
        if len(cleaned_secret) < 32:
            raise RuntimeError(
                f"Production startup rejected: JWT_SECRET is too weak. "
                f"HS256 requires at least 32 characters (256 bits), got {len(cleaned_secret)}."
            )

        # Entropy / character diversity check
        if len(set(cleaned_secret)) < 8:
            raise RuntimeError(
                "Production startup rejected: JWT_SECRET has insufficient entropy / character diversity."
            )

        # Known default / insecure secrets check
        normalized = cleaned_secret.lower()
        if normalized in KNOWN_INSECURE_SECRETS or any(pattern in normalized for pattern in INSECURE_SUBSTRINGS):
            raise RuntimeError(
                "Production startup rejected: JWT_SECRET is using a known default, example, or insecure secret. "
                "Production requires a unique, cryptographically strong secret."
            )

    return cleaned_secret


def get_jwt_secret() -> str:
    """Return active validated JWT secret."""
    return validate_jwt_secret()


# Validate immediately upon module load so invalid configuration halts application startup
JWT_SECRET = validate_jwt_secret()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    secret = get_jwt_secret()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        return None
    secret = get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except jwt.PyJWTError:
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    return user


def get_current_user_required(current_user: Optional[User] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
