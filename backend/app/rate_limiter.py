"""
RATE LIMITING MODULE

Provides IP-based and user-aware rate limiting for public and expensive endpoints
(especially LLM-backed endpoints like /requirements/analyze and /cv/analyze).

Supports:
- Shared distributed storage via Redis when REDIS_URL is configured (prevents multi-worker bypass).
- In-memory fallback (memory://) for local development and offline testing.
- Extraction of real client IP from X-Forwarded-For or X-Real-IP headers.
- Distinct limits for unauthenticated public requests vs. authenticated candidates.
"""

import os
from typing import Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging

logger = logging.getLogger(__name__)

# Configurable Rate Limits
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "1").lower() in ("1", "true", "yes")
RATE_LIMIT_REQUIREMENTS_ANALYZE = os.getenv("RATE_LIMIT_REQUIREMENTS_ANALYZE", "20/minute")
RATE_LIMIT_CV_ANALYZE = os.getenv("RATE_LIMIT_CV_ANALYZE", "10/minute")
RATE_LIMIT_AUTHENTICATED_TIER = os.getenv("RATE_LIMIT_AUTHENTICATED_TIER", "120/minute")

REDIS_URL = os.getenv("REDIS_URL")


def get_client_identifier(request: Request) -> str:
    """
    Extracts client identifier for rate limiting:
    1. If request has Authorization Bearer token, hash/use token prefix to allow higher authenticated quota.
    2. Otherwise, extract real client IP respecting X-Forwarded-For and X-Real-IP.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if len(token) > 10:
            return f"auth_user:{token[:16]}"

    # Fallback to remote IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in comma-separated list is client IP
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


# Configure SlowAPI Limiter with Redis (if provided) or In-Memory storage
storage_uri = REDIS_URL if REDIS_URL else "memory://"

try:
    limiter = Limiter(
        key_func=get_client_identifier,
        default_limits=[],
        storage_uri=storage_uri,
        enabled=RATE_LIMIT_ENABLED,
        headers_enabled=False,
    )
    if REDIS_URL:
        logger.info(f"Rate limiter initialized with Redis storage: {REDIS_URL}")
    else:
        logger.info("Rate limiter initialized with in-memory storage (local fallback)")
except Exception as e:
    logger.warning(f"Failed to initialize rate limiter with storage {storage_uri}: {e}. Falling back to memory://")
    limiter = Limiter(
        key_func=get_client_identifier,
        default_limits=[],
        storage_uri="memory://",
        enabled=RATE_LIMIT_ENABLED,
        headers_enabled=False,
    )
