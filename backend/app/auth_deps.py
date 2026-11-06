import os
import hashlib
import uuid
import logging
from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from app.database import SessionLocal, get_db
from app.models import User, RevokedToken

load_dotenv()

logger = logging.getLogger(__name__)

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

# Fast in-memory blocklist: token_hash -> expiry_timestamp
_in_memory_revocation_store: Dict[str, float] = {}

REDIS_URL = os.getenv("REDIS_URL")
_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not REDIS_URL:
        return None
    try:
        import redis
        client = redis.Redis.from_url(REDIS_URL, socket_timeout=1.5, socket_connect_timeout=1.5)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as err:
        logger.warning("Redis revocation client unavailable: %s", err)
        return None


def hash_token(token: str) -> str:
    """Compute SHA-256 hash of token to use as revocation key."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def revoke_token(token: str, db: Optional[Session] = None, user_id: Optional[int] = None) -> bool:
    """
    Revoke a JWT token so it cannot be reused.
    Multi-tier revocation store:
    1. In-memory fast cache (process local)
    2. Redis distributed cache (cross-process, TTL-managed)
    3. Database persistent revoked_tokens table (durability and fallback)
    """
    if not token or not str(token).strip():
        return False

    cleaned_token = token.strip()
    token_hash = hash_token(cleaned_token)
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    expires_at_dt = now_utc + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    try:
        unverified_payload = jwt.decode(
            cleaned_token,
            options={"verify_signature": False, "verify_exp": False},
        )
        exp_ts = unverified_payload.get("exp")
        if exp_ts:
            expires_at_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        if not user_id and unverified_payload.get("sub"):
            try:
                user_id = int(unverified_payload.get("sub"))
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    ttl = max(1, int(expires_at_dt.timestamp() - now_ts))

    # Tier 1: In-memory store
    _in_memory_revocation_store[token_hash] = expires_at_dt.timestamp()

    # Tier 2: Redis distributed store
    r = get_redis_client()
    if r:
        try:
            r.setex(f"revoked_token:{token_hash}", ttl, "1")
        except Exception as redis_err:
            logger.warning("Failed to persist revocation to Redis: %s", redis_err)

    # Tier 3: Database persistent store
    if db is not None:
        try:
            exists = db.query(RevokedToken).filter(RevokedToken.token_hash == token_hash).first()
            if not exists:
                revoked_record = RevokedToken(
                    token_hash=token_hash,
                    user_id=user_id,
                    expires_at=expires_at_dt.replace(tzinfo=None),
                )
                db.add(revoked_record)
                db.commit()
        except Exception as db_err:
            logger.warning("Failed to persist revocation to DB: %s", db_err)
            db.rollback()

    return True


def is_token_revoked(token: str, db: Optional[Session] = None) -> bool:
    """
    Check if a token has been revoked across all storage tiers.
    """
    if not token or not str(token).strip():
        return False

    token_hash = hash_token(token)
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()

    # Tier 1: In-memory store
    mem_exp = _in_memory_revocation_store.get(token_hash)
    if mem_exp is not None:
        if mem_exp > now_ts:
            return True
        else:
            _in_memory_revocation_store.pop(token_hash, None)

    # Tier 2: Redis store
    r = get_redis_client()
    if r:
        try:
            if r.exists(f"revoked_token:{token_hash}"):
                _in_memory_revocation_store[token_hash] = now_ts + 300
                return True
        except Exception as redis_err:
            logger.warning("Redis check failed: %s; falling back to DB/in-memory", redis_err)

    # Tier 3: Database store
    if db is not None:
        try:
            record = db.query(RevokedToken).filter(
                RevokedToken.token_hash == token_hash,
                RevokedToken.expires_at > now_utc.replace(tzinfo=None),
            ).first()
            if record:
                _in_memory_revocation_store[token_hash] = (
                    record.expires_at.replace(tzinfo=timezone.utc).timestamp()
                )
                return True
        except Exception as db_err:
            logger.warning("DB revocation check failed: %s", db_err)

    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    secret = get_jwt_secret()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    })
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        return None

    # Server-side token revocation rejection
    if is_token_revoked(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = get_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except jwt.PyJWTError:
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return None

    # Inactive account rejection
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_required(current_user: Optional[User] = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
