"""
OBSERVABILITY & TRACING MODULE

Provides:
- Request ID generation, bounding, validation, and tracing via ContextVar.
- Safe structured logging with automated sanitization of sensitive values
  (passwords, tokens, credentials, CV/JD texts, signed URLs).
- Standardized, safe API error responses with stable error codes and request IDs.
- Request lifecycle tracing middleware (route, method, status, duration).
"""

import os
import re
import time
import uuid
import logging
from contextvars import ContextVar
from typing import Optional, Dict, Any, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.observability")

# ContextVar storing the current request ID across async tasks and loggers
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# Request ID validation: bounded alphanumeric, hyphens, underscores, dots (1-128 chars)
REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")

# Patterns for sanitizing sensitive data from log records
SENSITIVE_PATTERNS = [
    # Passwords
    (re.compile(r'("?(?:password|current_password|new_password|password_hash)"?\s*[:=]\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'("?(?:password|current_password|new_password|password_hash)"?\s*[:=]\s*)[^\s,;&]+', re.IGNORECASE), r'\1[REDACTED]'),
    # Bearer tokens & JWTs
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.]+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'("?(?:access_token|refresh_token|token|reset_token|credential)"?\s*[:=]\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'("?(?:access_token|refresh_token|token|reset_token|credential)"?\s*[:=]\s*)[^\s,;&]+', re.IGNORECASE), r'\1[REDACTED]'),
    # API keys / credentials
    (re.compile(r'("?(?:api_key|apikey|secret_key|aws_secret_access_key|aws_access_key_id)"?\s*[:=]\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'("?(?:api_key|apikey|secret_key|aws_secret_access_key|aws_access_key_id)"?\s*[:=]\s*)[^\s,;&]+', re.IGNORECASE), r'\1[REDACTED]'),
    # S3 / Cloud Storage presigned URLs & signatures
    (re.compile(r'(X-Amz-Signature=[a-fA-F0-9]+)', re.IGNORECASE), r'X-Amz-Signature=[REDACTED]'),
    (re.compile(r'(Signature=[^&\s]+)', re.IGNORECASE), r'Signature=[REDACTED]'),
    (re.compile(r'(X-Amz-Credential=[^&\s]+)', re.IGNORECASE), r'X-Amz-Credential=[REDACTED]'),
    (re.compile(r'(X-Amz-Security-Token=[^&\s]+)', re.IGNORECASE), r'X-Amz-Security-Token=[REDACTED]'),
]

STATUS_CODE_TO_ERROR_CODE: Dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    502: "AI_PROVIDER_ERROR",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def is_valid_request_id(req_id: Optional[str]) -> bool:
    """Validates that a request ID is non-empty, bounded to 128 chars, and safe."""
    if not req_id or not isinstance(req_id, str):
        return False
    stripped = req_id.strip()
    return bool(REQUEST_ID_REGEX.match(stripped))


def generate_request_id() -> str:
    """Generates a clean, unique request ID."""
    return f"req_{uuid.uuid4().hex}"


def resolve_request_id(incoming: Optional[str]) -> str:
    """
    Accepts and bounds an incoming request ID if valid;
    otherwise generates a new safe request ID.
    """
    if incoming and is_valid_request_id(incoming):
        return incoming.strip()
    return generate_request_id()


def get_current_request_id() -> str:
    """Retrieves current request ID from contextvar or returns empty string."""
    return request_id_ctx.get()


def mask_sensitive_data(text: str) -> str:
    """Scans and masks sensitive patterns in log messages."""
    if not text or not isinstance(text, str):
        return text
    masked = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


class SafeLogFilter(logging.Filter):
    """
    Logging filter that:
    1. Injects request_id into every log record.
    2. Masks sensitive data (passwords, tokens, credentials, signatures).
    """
    def filter(self, record: logging.LogRecord) -> bool:
        req_id = get_current_request_id()
        record.request_id = req_id if req_id else "-"

        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: mask_sensitive_data(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(mask_sensitive_data(str(a)) if isinstance(a, str) else a for a in record.args)

        return True


class StructuredLogFormatter(logging.Formatter):
    """Formats log records with timestamp, level, request_id, and message."""
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        default_fmt = "%(asctime)s [%(levelname)s] [request_id=%(request_id)s] %(name)s: %(message)s"
        super().__init__(fmt or default_fmt, datefmt or "%Y-%m-%d %H:%M:%S")


def setup_logging(level: int = logging.INFO):
    """Configures structured, sanitized logging on root and application loggers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers on re-setup
    has_safe_handler = any(isinstance(f, SafeLogFilter) for h in root_logger.handlers for f in h.filters)
    if not has_safe_handler:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredLogFormatter())
        handler.addFilter(SafeLogFilter())
        root_logger.addHandler(handler)


def get_error_code_for_status(status_code: int, detail: Optional[str] = None) -> str:
    """Maps status code and message to stable error codes."""
    detail_lower = str(detail or "").lower()

    if status_code == 400:
        if "pdf" in detail_lower or "file" in detail_lower or "upload" in detail_lower:
            return "INVALID_FILE"
        if "requirement" in detail_lower or "job description" in detail_lower:
            return "INVALID_REQUIREMENTS"
        if "reset token" in detail_lower:
            return "INVALID_RESET_TOKEN"
        return "BAD_REQUEST"

    if status_code == 401:
        if "expired" in detail_lower or "session" in detail_lower:
            return "SESSION_EXPIRED"
        return "INVALID_CREDENTIALS"

    if status_code == 403:
        if "deactivated" in detail_lower:
            return "ACCOUNT_DEACTIVATED"
        return "FORBIDDEN"

    if status_code == 404:
        if "session" in detail_lower:
            return "SESSION_NOT_FOUND"
        if "cv" in detail_lower:
            return "CV_NOT_FOUND"
        if "attempt" in detail_lower:
            return "ATTEMPT_NOT_FOUND"
        return "NOT_FOUND"

    if status_code == 409:
        if "email" in detail_lower or "already registered" in detail_lower:
            return "EMAIL_ALREADY_EXISTS"
        return "CONFLICT"

    if status_code == 502:
        return "AI_PROVIDER_ERROR"

    if status_code == 503:
        return "SERVICE_UNAVAILABLE"

    return STATUS_CODE_TO_ERROR_CODE.get(status_code, "API_ERROR")


def get_safe_error_message(status_code: int, detail: Any) -> str:
    """
    Returns a safe, user-friendly error message, concealing internal stack traces,
    raw database errors, and raw AI provider errors from the HTTP response.
    """
    if status_code == 500:
        return "Internal server error"

    if status_code == 502:
        return "The AI analysis service is temporarily unavailable. Please try again in a few moments."

    if status_code == 503:
        # Allow readiness failure details through if they are structured messages
        if isinstance(detail, str) and ("service unavailable" in detail.lower() or "readiness" in detail.lower()):
            return detail
        return "Service temporarily unavailable. Please try again later."

    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):
        # Format Pydantic validation error list
        items = []
        for item in detail:
            if isinstance(item, dict):
                loc = " -> ".join(str(l) for l in item.get("loc", []))
                msg = item.get("msg", "Invalid value")
                items.append(f"{loc}: {msg}" if loc else msg)
            else:
                items.append(str(item))
        return "; ".join(items) if items else "Invalid request data"

    if isinstance(detail, dict):
        return detail.get("message") or detail.get("detail") or "Request failed"

    return "An unexpected error occurred"


def build_cors_headers(request: Request) -> Dict[str, str]:
    """Generates standard CORS response headers based on request Origin and config."""
    frontend_origins_str = os.getenv("FRONTEND_ORIGINS", "")
    frontend_origins = [o.strip() for o in frontend_origins_str.split(",") if o.strip()]

    headers = {
        "Access-Control-Expose-Headers": "X-Request-ID, Retry-After",
    }
    origin = request.headers.get("origin")
    if origin and (origin in frontend_origins or not frontend_origins or "*" in frontend_origins):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers


def create_error_response(
    request: Request,
    status_code: int,
    detail: Any,
    error_code: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """
    Constructs a consistent API error response with:
    - Stable error_code
    - Safe message (detail)
    - Request ID (in body and header)
    - CORS headers
    """
    req_id = (
        getattr(request.state, "request_id", None)
        or get_current_request_id()
        or generate_request_id()
    )

    safe_message = get_safe_error_message(status_code, detail)
    code = error_code or get_error_code_for_status(status_code, safe_message)

    resp_headers = build_cors_headers(request)
    resp_headers["X-Request-ID"] = req_id
    if headers:
        resp_headers.update(headers)

    content = {
        "detail": safe_message,
        "error_code": code,
        "request_id": req_id,
        "error": {
            "code": code,
            "message": safe_message,
            "request_id": req_id,
        },
    }

    return JSONResponse(status_code=status_code, content=content, headers=resp_headers)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    ASGI Middleware that:
    1. Extracts or generates bounded X-Request-ID for each request.
    2. Binds request ID to ContextVar and request.state.
    3. Returns X-Request-ID and CORS exposure headers on all responses.
    4. Logs request route, method, status, duration, and safe failure info.
    """
    async def dispatch(self, request: Request, call_next):
        raw_header = request.headers.get("x-request-id")
        req_id = resolve_request_id(raw_header)

        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response.headers["X-Request-ID"] = req_id
            # Ensure JavaScript can read X-Request-ID header
            expose_existing = response.headers.get("Access-Control-Expose-Headers", "")
            if "X-Request-ID" not in expose_existing:
                expose_new = f"{expose_existing}, X-Request-ID, Retry-After".strip(", ")
                response.headers["Access-Control-Expose-Headers"] = expose_new

            client_ip = (
                request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                or request.headers.get("x-real-ip", "")
                or (request.client.host if request.client else "unknown")
            )

            # Structured request completion log
            path = request.url.path
            method = request.method
            status = response.status_code

            if status >= 500:
                logger.error(
                    f"Request failed: {method} {path} status={status} duration={duration_ms}ms "
                    f"ip={client_ip} request_id={req_id}"
                )
            elif status >= 400:
                logger.warning(
                    f"Request client error: {method} {path} status={status} duration={duration_ms}ms "
                    f"ip={client_ip} request_id={req_id}"
                )
            else:
                logger.info(
                    f"Request completed: {method} {path} status={status} duration={duration_ms}ms "
                    f"ip={client_ip} request_id={req_id}"
                )

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path} "
                f"duration={duration_ms}ms [request_id={req_id}]: {exc}",
                exc_info=True,
            )
            return create_error_response(
                request=request,
                status_code=500,
                detail="Internal server error",
                error_code="INTERNAL_SERVER_ERROR",
            )
        finally:
            request_id_ctx.reset(token)
