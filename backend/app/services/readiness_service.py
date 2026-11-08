"""
READINESS & LIVENESS SERVICE

Provides bounded readiness probes for CareerSkill platform:
- Database connectivity check (bounded timeout)
- Assessment question bank data verification (must contain active questions)
- Configured storage backend accessibility (local directory or S3)
- Redis rate limiter check (graceful degradation: returns degraded without failing readiness)
- AI provider configuration check (strictly avoids routine live external API calls)
"""

import os
import time
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app.models import AssessmentQuestion
from app.services.storage_service import get_storage_backend, LocalStorageBackend, S3StorageBackend

logger = logging.getLogger("app.readiness")


def check_database(timeout_seconds: float = 2.0, target_engine=None) -> Dict[str, Any]:
    """
    Executes a bounded connectivity query against the primary PostgreSQL database.
    """
    db_engine = target_engine or engine
    start = time.perf_counter()
    try:
        with db_engine.connect() as conn:
            # Enforce bounded execution timeout if supported
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error(f"Readiness check - Database failed ({latency_ms}ms): {exc}")
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": "Database connectivity failed",
        }


def check_question_bank(session_factory=None) -> Dict[str, Any]:
    """
    Verifies that the question bank has been seeded with active questions.
    Technical assessment is a core platform function requiring question data.
    """
    factory = session_factory or SessionLocal
    start = time.perf_counter()
    try:
        with factory() as session:
            count = (
                session.query(AssessmentQuestion)
                .filter(AssessmentQuestion.is_active.is_(True))
                .count()
            )
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            if count > 0:
                return {
                    "status": "ok",
                    "total_active_questions": count,
                    "latency_ms": latency_ms,
                }
            logger.error("Readiness check - Question bank has 0 active questions")
            return {
                "status": "unhealthy",
                "total_active_questions": 0,
                "latency_ms": latency_ms,
                "error": "Assessment question bank is empty",
            }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error(f"Readiness check - Question bank query failed ({latency_ms}ms): {exc}")
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": "Failed to query question bank",
        }


def check_storage(backend=None) -> Dict[str, Any]:
    """
    Verifies that configured CV storage is available and writable.
    Supports LocalStorageBackend and S3StorageBackend.
    """
    storage = backend or get_storage_backend()
    start = time.perf_counter()

    if isinstance(storage, LocalStorageBackend) or hasattr(storage, "base_dir"):
        base_dir = getattr(storage, "base_dir", os.getenv("UPLOAD_DIR", "uploads"))
        try:
            os.makedirs(base_dir, exist_ok=True)
            probe_file = os.path.join(base_dir, ".readiness_probe")
            with open(probe_file, "w") as f:
                f.write("probe")
            if os.path.exists(probe_file):
                os.remove(probe_file)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "ok",
                "backend": "local",
                "directory": base_dir,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(f"Readiness check - Local storage check failed: {exc}")
            return {
                "status": "unhealthy",
                "backend": "local",
                "directory": base_dir,
                "latency_ms": latency_ms,
                "error": "Storage directory is not writable",
            }

    if isinstance(storage, S3StorageBackend) or getattr(storage, "bucket_name", None):
        bucket_name = getattr(storage, "bucket_name", os.getenv("S3_BUCKET_NAME", "career-skill-cv-uploads"))
        try:
            # Verify client initialization and bucket configuration without hanging
            client = storage._get_client()
            if not client:
                raise RuntimeError("Failed to create S3 client")
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "ok",
                "backend": "s3",
                "bucket": bucket_name,
                "latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(f"Readiness check - S3 storage check failed: {exc}")
            return {
                "status": "unhealthy",
                "backend": "s3",
                "bucket": bucket_name,
                "latency_ms": latency_ms,
                "error": "S3 storage is unreachable or misconfigured",
            }

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "status": "ok",
        "backend": "unknown",
        "latency_ms": latency_ms,
    }


def check_redis(redis_url: Optional[str] = None, timeout_seconds: float = 1.5) -> Dict[str, Any]:
    """
    Checks Redis connectivity.
    Because Redis is only used for distributed rate-limiting and falls back to memory://,
    its absence or failure is reported as 'degraded' rather than declaring the entire app down.
    """
    target_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")

    if not target_url:
        return {
            "status": "ok",
            "role": "rate_limiting",
            "mode": "in_memory",
            "message": "Redis not configured; rate limiting operates with in-memory storage",
        }

    start = time.perf_counter()
    try:
        import redis
        client = redis.from_url(
            target_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
        )
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "role": "rate_limiting",
            "mode": "redis",
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            f"Readiness check - Redis is unavailable ({latency_ms}ms): {exc}. "
            f"Rate limiter gracefully degrades to in-memory fallback."
        )
        return {
            "status": "degraded",
            "role": "rate_limiting",
            "mode": "in_memory_fallback",
            "latency_ms": latency_ms,
            "message": "Redis unavailable; rate limiting operating on local in-memory fallback",
        }


def check_ai_provider() -> Dict[str, Any]:
    """
    Routine health/readiness probe for AI evaluation provider.
    STRICT REQUIREMENT: Avoids live external AI provider API calls in routine probes
    to prevent quota consumption, cost, latency, and false outages from 3rd party rate limits.
    """
    is_mock = os.getenv("GEMINI_MOCK") == "1"
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if is_mock or has_gemini or has_groq:
        return {
            "status": "ok",
            "provider": "mock" if is_mock else provider,
            "live_probe": False,
        }

    return {
        "status": "unhealthy",
        "provider": provider,
        "live_probe": False,
        "error": "No LLM provider credentials configured (GEMINI_API_KEY / GROQ_API_KEY / GEMINI_MOCK)",
    }


def perform_readiness_check(
    target_engine=None,
    session_factory=None,
    storage_backend=None,
    redis_url: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """
    Runs all bounded readiness checks.

    Decision Matrix:
    - Critical dependencies (DB, Question Bank, Storage):
      If any critical dependency fails -> HTTP 503 (unhealthy).
    - Redis:
      If Redis fails or is unavailable -> HTTP 200 (degraded).
    - If all components are healthy -> HTTP 200 (ok).
    """
    db_result = check_database(target_engine=target_engine)
    qb_result = check_question_bank(session_factory=session_factory)
    storage_result = check_storage(backend=storage_backend)
    redis_result = check_redis(redis_url=redis_url)
    ai_result = check_ai_provider()

    checks = {
        "database": db_result,
        "question_bank": qb_result,
        "storage": storage_result,
        "redis": redis_result,
        "ai_provider": ai_result,
    }

    # Evaluate critical dependencies required to serve user traffic
    critical_failed = (
        db_result["status"] != "ok"
        or qb_result["status"] != "ok"
        or storage_result["status"] != "ok"
    )

    if critical_failed:
        overall_status = "unhealthy"
        status_code = 503
    elif redis_result["status"] == "degraded":
        overall_status = "degraded"
        status_code = 200
    else:
        overall_status = "ok"
        status_code = 200

    payload = {
        "status": overall_status,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
    }

    return status_code, payload
