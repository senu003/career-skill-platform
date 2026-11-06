import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.models import AnalysisRequest
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Timeout in seconds before an in-flight 'processing' request is considered stale/abandoned
IDEMPOTENCY_PROCESSING_TIMEOUT_SECONDS = 300


def compute_analysis_request_hash(
    requirements: str,
    job_title: Optional[str] = None,
    company: Optional[str] = None,
    include_prior: bool = False,
    file_bytes: Optional[bytes] = None,
    cv_id: Optional[int] = None,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of the analysis request inputs.
    Normalizes requirements JSON / string and input metadata.
    """
    hasher = hashlib.sha256()

    # Normalize requirements
    norm_req = requirements.strip() if requirements else ""
    try:
        parsed = json.loads(norm_req)
        norm_req = json.dumps(parsed, sort_keys=True)
    except Exception:
        pass
    hasher.update(norm_req.encode("utf-8"))

    # Normalize job title and company
    hasher.update((job_title or "").strip().lower().encode("utf-8"))
    hasher.update((company or "").strip().lower().encode("utf-8"))
    hasher.update(b"1" if include_prior else b"0")

    # Include file content or saved cv_id
    if file_bytes is not None:
        hasher.update(b"file:")
        hasher.update(file_bytes)
    elif cv_id is not None:
        hasher.update(f"cv_id:{cv_id}".encode("utf-8"))
    else:
        hasher.update(b"no_file_or_id")

    return hasher.hexdigest()


def register_or_get_analysis_request(
    db: Session,
    user_id: int,
    idempotency_key: str,
    request_hash: str,
) -> Tuple[AnalysisRequest, bool]:
    """
    Registers or retrieves an idempotency record scoped to the authenticated user.
    
    Returns (record, is_new):
      - is_new=True: Caller should proceed with analysis execution.
      - is_new=False: Already completed; caller should return the saved result.

    Enforces:
      - 409 Conflict if key is reused with different request parameters.
      - 409 Conflict if key is currently being processed by a concurrent request.
    """
    existing = (
        db.query(AnalysisRequest)
        .filter(
            AnalysisRequest.user_id == user_id,
            AnalysisRequest.idempotency_key == idempotency_key,
        )
        .first()
    )

    if existing:
        # 1. Reject reuse of the same key with different inputs
        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key has already been used with different request parameters."
            )

        # 2. If already completed, return existing saved record
        if existing.status == "completed":
            return existing, False

        # 3. If processing, check for stale/abandoned timeout
        if existing.status == "processing":
            now = datetime.now(timezone.utc)
            updated_at = existing.updated_at
            if updated_at is not None:
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                age = (now - updated_at).total_seconds()
            else:
                age = 0

            if age < IDEMPOTENCY_PROCESSING_TIMEOUT_SECONDS:
                raise HTTPException(
                    status_code=409,
                    detail="Analysis request with this idempotency key is currently being processed. Please wait or retry shortly."
                )
            else:
                # Stale processing request, take over execution
                logger.warning(f"Reclaiming stale processing request {existing.id} for user {user_id}")
                existing.status = "processing"
                existing.updated_at = func.now()
                db.commit()
                db.refresh(existing)
                return existing, True

        # 4. If previously failed, allow retry with same inputs
        if existing.status == "failed":
            existing.status = "processing"
            existing.updated_at = func.now()
            db.commit()
            db.refresh(existing)
            return existing, True

    # No existing record: create and commit a 'processing' record
    try:
        new_record = AnalysisRequest(
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing"
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record, True
    except IntegrityError:
        db.rollback()
        # Concurrent insert won race condition; query and re-evaluate
        winner = (
            db.query(AnalysisRequest)
            .filter(
                AnalysisRequest.user_id == user_id,
                AnalysisRequest.idempotency_key == idempotency_key,
            )
            .first()
        )
        if not winner:
            raise
        if winner.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key has already been used with different request parameters."
            )
        if winner.status == "completed":
            return winner, False
        raise HTTPException(
            status_code=409,
            detail="Analysis request with this idempotency key is currently being processed. Please wait or retry shortly."
        )


def mark_analysis_request_failed(request_id: Optional[int]) -> None:
    """
    Marks an analysis request as failed in an independent session
    so the status is preserved even if the main transaction rolled back.
    """
    if not request_id:
        return
    session = SessionLocal()
    try:
        record = session.query(AnalysisRequest).filter(AnalysisRequest.id == request_id).first()
        if record and record.status != "completed":
            record.status = "failed"
            record.updated_at = func.now()
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Failed to mark analysis request {request_id} as failed: {e}")
    finally:
        session.close()

