import os
import json
import logging
from typing import Optional, List, Dict, Any

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from .pdf_service import extract_pdf_text
from .storage_service import get_storage_backend


logger = logging.getLogger(__name__)

# Default maximum upload limit: 10 MB (10,485,760 bytes)
DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def get_max_upload_size_bytes() -> int:
    mb_env = os.getenv("MAX_UPLOAD_SIZE_MB")
    if mb_env:
        try:
            return int(float(mb_env) * 1024 * 1024)
        except (ValueError, TypeError):
            pass
    try:
        return int(os.getenv("MAX_CV_UPLOAD_SIZE_BYTES", str(DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES


def get_max_upload_size_mb() -> float:
    return get_max_upload_size_bytes() / (1024 * 1024)


async def read_bounded_file(file: UploadFile, max_bytes: int) -> bytes:
    """
    Safely reads uploaded file stream up to max_bytes without buffering oversized payloads into RAM.
    Rejects early if reported content length exceeds max_bytes.
    """
    # 1. Early rejection based on file.size (Content-Length header)
    if file.size is not None and file.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of {max_mb}MB."
        )

    # 2. Chunked stream reading
    content = bytearray()
    chunk_size = 64 * 1024  # 64 KB chunks
    try:
        await file.seek(0)
    except Exception:
        pass

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed limit of {max_mb}MB."
            )

    return bytes(content)


def extract_text_from_storage(storage_path_or_key: str) -> dict:
    """
    Extracts text from a CV stored either on the local filesystem or in private object storage (S3).
    Handles temporary scratch file extraction safely for non-local backends with guaranteed cleanup.
    """
    if not storage_path_or_key:
        raise HTTPException(status_code=400, detail="Storage path cannot be empty.")

    # 1. Direct local file check
    if os.path.exists(storage_path_or_key):
        return extract_pdf_text(storage_path_or_key)

    # 2. Storage backend retrieval (S3 or local relative)
    storage = get_storage_backend()
    try:
        content = storage.get_file_bytes(storage_path_or_key)
    except Exception as e:
        logger.warning(f"Failed to retrieve file from storage {storage_path_or_key}: {e}")
        # Backward-compatible fallback for relative local path
        if hasattr(storage, "_resolve_safe_path"):
            safe_p = storage._resolve_safe_path(storage_path_or_key)
            if os.path.exists(safe_p):
                return extract_pdf_text(safe_p)
        raise HTTPException(status_code=404, detail="CV file could not be retrieved from storage.")

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return extract_pdf_text(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


async def process_cv(
    file: UploadFile,
    user_id: Optional[int] = None,
    max_size_bytes: Optional[int] = None
) -> dict:
    """
    Processes an uploaded CV PDF file:
    1. Validates that the file has a PDF extension and MIME type.
    2. Enforces configurable upload size limit (default 10 MB).
    3. Rejects empty files or files lacking standard %PDF- header magic bytes.
    4. Saves the file using persistent storage backend (local disk or private S3).
    5. Extracts text across all pages using pdf_service.
    6. Returns structured JSON containing filename, file_path, page count, and full text.
    """
    filename = file.filename or ""

    # Validate file format (check MIME type or extension)
    is_pdf_mime = file.content_type in ["application/pdf", "application/x-pdf", "binary/octet-stream"]
    is_pdf_ext = filename.lower().endswith(".pdf")

    if not (is_pdf_mime or is_pdf_ext) or (not is_pdf_ext and file.content_type not in ["application/pdf", "application/x-pdf"]):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Read uploaded file content with strict size boundary enforcement
    limit = max_size_bytes or get_max_upload_size_bytes()
    content = await read_bounded_file(file, limit)

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    # Reject non-PDF or corrupted files lacking magic bytes signature
    if not (content.startswith(b"%PDF") or b"%PDF" in content[:1024]):
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file: Missing %PDF signature header."
        )

    # Save file via storage abstraction
    storage = get_storage_backend()
    storage_key, file_path = storage.save_file(content, filename, user_id=user_id)

    # Extract text from PDF via unified storage helper
    pdf_data = extract_text_from_storage(file_path)

    return {
        "filename": file.filename,
        "file_path": file_path,
        "storage_key": storage_key,
        "pages": pdf_data["pages"],
        "text": pdf_data["text"],
        "parsing_method": pdf_data.get("parsing_method", "unknown"),
        "parse_quality_score": pdf_data.get("parse_quality_score", 0.0)
    }


def parse_and_validate_requirements(requirements_str: str) -> List[Dict[str, Any]]:
    """
    Parses and validates the JSON string containing skill requirements.
    Enforces required structure: non-empty list of dicts with 'skill', 'level', 'importance'.
    """
    if not requirements_str or not requirements_str.strip():
        raise HTTPException(
            status_code=400,
            detail="Requirements string cannot be empty."
        )

    try:
        data = json.loads(requirements_str)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid requirements JSON format."
        )

    if not isinstance(data, list):
        raise HTTPException(
            status_code=400,
            detail="Requirements JSON must be a list."
        )

    if len(data) == 0:
        raise HTTPException(
            status_code=400,
            detail="Requirements list cannot be empty."
        )

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Requirement item at index {idx} must be an object."
            )

        if "skill" not in item or not isinstance(item["skill"], str) or not item["skill"].strip():
            raise HTTPException(
                status_code=400,
                detail=f"Requirement item at index {idx} missing 'skill'."
            )

        if "level" not in item or not isinstance(item["level"], str) or not item["level"].strip():
            raise HTTPException(
                status_code=400,
                detail=f"Requirement item at index {idx} missing 'level'."
            )

        if "importance" not in item or not isinstance(item["importance"], str) or not item["importance"].strip():
            raise HTTPException(
                status_code=400,
                detail=f"Requirement item at index {idx} missing 'importance'."
            )

    return data


def get_candidate_sessions(db: Session, user_id: int) -> List[dict]:
    """
    Retrieves past job requirement & match analysis sessions for the candidate with summary statistics.
    """
    from app.models import Analysis, Job, CV
    from app.services.scoring_service import calculate_skill_score
    from app.services.skill_analysis_service import combine_cv_and_assessment

    analyses = db.query(Analysis).filter(Analysis.user_id == user_id).order_by(Analysis.created_at.desc()).all()
    sessions = []

    latest_cv = db.query(CV).filter(CV.user_id == user_id).order_by(CV.uploaded_at.desc()).first()

    for a in analyses:
        job = db.query(Job).filter(Job.id == a.job_id).first()
        cv_obj = db.query(CV).filter(CV.id == a.cv_id).first()
        if not cv_obj:
            cv_obj = latest_cv

        parsed_skills = []
        job_desc = getattr(job, "description", None) if job else None
        if job_desc is not None:
            try:
                parsed_skills = json.loads(str(job_desc))
            except Exception:
                pass

        score_data = {"score": 0, "matched_count": 0, "missing_count": 0, "total_skills": 0}
        combined = {"skills": []}

        if parsed_skills:
            raw_analysis = getattr(a, "raw_analysis_data", None)
            if raw_analysis is not None:
                try:
                    evaluated_skills = json.loads(str(raw_analysis))
                except Exception:
                    evaluated_skills = []
            else:
                evaluated_skills = []

            if not evaluated_skills:
                evaluated_skills = [
                    {"skill": s.get("skill"), "required_level": s.get("level", "unspecified"), "importance": s.get("importance", "required"), "cv_level": "not_found", "cv_match_status": "Missing", "evidence": None}
                    for s in parsed_skills if isinstance(s, dict)
                ]
            matched_skills = [s for s in evaluated_skills if s.get("cv_match_status") == "Match"]
            missing_skills = [s for s in evaluated_skills if s.get("cv_match_status") != "Match"]
            score_data = calculate_skill_score(matched_skills, missing_skills)
            analysis_id_val = int(str(getattr(a, "id"))) if getattr(a, "id", None) is not None else None
            combined = combine_cv_and_assessment({
                "skills": evaluated_skills,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "score_data": score_data
            }, db, user_id, analysis_id_val)

        skills_list = combined.get("skills", [])
        total_skills_count = len(skills_list) if skills_list else len(parsed_skills)
        matched_skills_count = len([s for s in skills_list if s.get("matched") and not s.get("is_weakness")]) if skills_list else score_data.get("matched_count", 0)
        improvement_skills_count = len([s for s in skills_list if s.get("is_weakness") or not s.get("matched")]) if skills_list else score_data.get("missing_count", 0)

        score_val = float(str(a.overall_score)) if a.overall_score is not None else float(score_data.get("score", 0))

        if score_val >= 80:
            overall_readiness = "Advanced"
        elif score_val >= 60:
            overall_readiness = "Intermediate"
        elif score_val >= 40:
            overall_readiness = "Basic"
        else:
            overall_readiness = "Foundational"

        assessed_count = len([s for s in skills_list if s.get("assessed_level") is not None])
        assessment_status = "Completed" if assessed_count > 0 or total_skills_count > 0 else "Pending"

        sessions.append({
            "analysis_id": a.id,
            "job_id": a.job_id,
            "job_title": job.title if job else "Job Position",
            "company": job.company if job else "",
            "requirements": job.description if job else "",
            "parsed_skills": parsed_skills,
            "skills": skills_list,
            "cv_filename": cv_obj.file_name if cv_obj else "Uploaded Resume",
            "overall_score": score_val,
            "total_skills_count": total_skills_count,
            "matched_skills_count": matched_skills_count,
            "improvement_skills_count": improvement_skills_count,
            "assessment_status": assessment_status,
            "overall_readiness": overall_readiness,
            "final_verdict": combined.get("final_verdict") or combined.get("readiness_verdict") or overall_readiness,
            "readiness_verdict": combined.get("readiness_verdict") or combined.get("final_verdict") or overall_readiness,
            "is_preliminary": combined.get("is_preliminary", True),
            "recommendation_confidence": combined.get("recommendation_confidence"),
            "assessed_skills_count": assessed_count,
            "status_badge": "Analysis Complete",
            "created_at": getattr(a, "created_at").isoformat() if getattr(a, "created_at", None) is not None else None
        })
    return sessions


def get_candidate_session_detail(
    db: Session,
    analysis_id: int,
    user_id: int,
    force_reanalyze: bool = False
) -> dict:
    """
    Retrieves full analysis result details for a specific historical session.
    """
    from app.models import Analysis, Job, CV
    from app.services.requirement_service import evaluate_cv_with_gemini
    from app.services.scoring_service import calculate_skill_score
    from app.services.skill_analysis_service import combine_cv_and_assessment

    analysis_record = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user_id).first()
    if not analysis_record:
        raise HTTPException(status_code=404, detail="Analysis session not found.")

    job_record = db.query(Job).filter(Job.id == analysis_record.job_id).first()
    cv_record = db.query(CV).filter(CV.id == analysis_record.cv_id).first()
    if not cv_record:
        cv_record = db.query(CV).filter(CV.user_id == user_id).order_by(CV.uploaded_at.desc()).first()

    job_desc = getattr(job_record, "description", None) if job_record else None
    parsed_requirements = parse_and_validate_requirements(str(job_desc)) if job_desc else []

    cv_text = ""
    cv_path = getattr(cv_record, "file_path", None) if cv_record else None
    if cv_path and os.path.exists(str(cv_path)):
        pdf_data = extract_pdf_text(str(cv_path))
        cv_text = pdf_data.get("text", "")

    raw_data = getattr(analysis_record, "raw_analysis_data", None)
    if raw_data and not force_reanalyze:
        evaluated_skills = json.loads(str(raw_data))
    else:
        if not force_reanalyze and not raw_data:
            evaluated_skills = [
                {
                    "skill": s.get("skill"), 
                    "required_level": s.get("level", "unspecified"), 
                    "importance": s.get("importance", "required"), 
                    "cv_level": "unspecified", 
                    "cv_match_status": "Missing", 
                    "evidence": None,
                    "actionable_feedback": None
                }
                for s in parsed_requirements if isinstance(s, dict)
            ]
        else:
            evaluated_skills = evaluate_cv_with_gemini(cv_text, parsed_requirements) if cv_text else []
            if not evaluated_skills:
                evaluated_skills = [
                    {"skill": s.get("skill"), "required_level": s.get("level", "unspecified"), "importance": s.get("importance", "required"), "cv_level": "not_found", "cv_match_status": "Missing", "evidence": None, "actionable_feedback": None}
                    for s in parsed_requirements if isinstance(s, dict)
                ]
            
            if force_reanalyze:
                setattr(analysis_record, "raw_analysis_data", json.dumps(evaluated_skills))
                db.commit()

    matched_skills = [s for s in evaluated_skills if s.get("cv_match_status") == "Match"]
    missing_skills = [s for s in evaluated_skills if s.get("cv_match_status") != "Match"]
    score_data = calculate_skill_score(matched_skills, missing_skills)

    cv_matching_result = {
        "filename": getattr(cv_record, "file_name", "Resume.pdf") if cv_record else "Resume.pdf",
        "pages": 1,
        "skills": evaluated_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score_data": score_data
    }

    analysis_record_id = int(str(getattr(analysis_record, "id"))) if getattr(analysis_record, "id", None) is not None else None
    result = combine_cv_and_assessment(
        cv_matching_result,
        db_or_assessments=db,
        user_id=user_id,
        analysis_id=analysis_record_id,
    )
    result["job_title"] = job_record.title if job_record else "Job Position"
    result["company"] = job_record.company if job_record else ""
    result["analysis_id"] = analysis_record_id
    return result
