import json
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Depends, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

import tempfile
from app.database import get_db
from app.services import cv_service
from app.services.cv_service import (
    process_cv,
    extract_pdf_text,
    parse_and_validate_requirements,
    get_candidate_sessions,
    get_candidate_session_detail,
    read_bounded_file,
    get_max_upload_size_bytes,
)
from app.services.idempotency_service import (
    compute_analysis_request_hash,
    register_or_get_analysis_request,
    mark_analysis_request_failed,
)
from app.services.requirement_service import extract_requirements, evaluate_cv_with_gemini
from app.services.matching_service import match_skills_in_text
from app.services.scoring_service import calculate_skill_score
from app.services.skill_analysis_service import combine_cv_and_assessment
from app.schemas.cv import CVAnalyzeResponseSchema
from app.auth_deps import get_current_user, get_current_user_required, User
from app.models import CV, Job, Analysis, AnalysisRequest
from app.rate_limiter import limiter, RATE_LIMIT_CV_ANALYZE
from app.services.storage_service import get_storage_backend

logger = logging.getLogger(__name__)

router = APIRouter()






@router.get("/cv/latest")
def get_latest_cv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Retrieves the authenticated candidate's most recently uploaded CV record.
    """
    cv_record = db.query(CV).filter(CV.user_id == current_user.id).order_by(CV.uploaded_at.desc()).first()
    if not cv_record:
        return {"has_cv": False, "cv": None}
    cv_up = getattr(cv_record, "uploaded_at", None)
    return {
        "has_cv": True,
        "cv": {
            "id": getattr(cv_record, "id", None),
            "file_name": getattr(cv_record, "file_name", None),
            "uploaded_at": cv_up.isoformat() if cv_up is not None else None
        }
    }


@router.get("/cv/all")
def get_all_cvs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Retrieves all uploaded CV records for the authenticated candidate with analysis counts.
    """
    cv_records = db.query(CV).filter(CV.user_id == current_user.id).order_by(CV.uploaded_at.desc()).all()
    if not cv_records:
        return {"has_cv": False, "count": 0, "cvs": []}

    # Count analyses per CV
    analysis_counts = {}
    counts = (
        db.query(Analysis.cv_id, func.count(Analysis.id))
        .filter(Analysis.user_id == current_user.id)
        .group_by(Analysis.cv_id)
        .all()
    )
    for cid, cnt in counts:
        if cid is not None:
            analysis_counts[cid] = cnt

    latest_id = cv_records[0].id if cv_records else None

    cvs = []
    for cv in cv_records:
        cv_up = getattr(cv, "uploaded_at", None)
        cvs.append({
            "id": getattr(cv, "id", None),
            "file_name": getattr(cv, "file_name", None),
            "uploaded_at": cv_up.isoformat() if cv_up is not None else None,
            "is_default": (cv.id == latest_id),
            "analyses_count": analysis_counts.get(cv.id, 0)
        })

    return {
        "has_cv": True,
        "count": len(cvs),
        "cvs": cvs
    }


@router.post("/cv/{cv_id}/set-default")
def set_default_cv(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Sets a CV as the default/active CV by updating its uploaded_at timestamp.
    """
    cv = db.query(CV).filter(CV.id == cv_id, CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    cv.uploaded_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "CV set as default", "id": cv_id}


@router.get("/cv/{cv_id}/download")
def download_cv(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Downloads or previews an uploaded CV file.
    """
    cv = db.query(CV).filter(CV.id == cv_id, CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    file_bytes = None
    try:
        storage = get_storage_backend()
        file_bytes = storage.get_file_bytes(cv.file_path)
    except Exception:
        if cv.file_path and os.path.exists(cv.file_path):
            with open(cv.file_path, "rb") as f:
                file_bytes = f.read()

    if not file_bytes:
        raise HTTPException(status_code=404, detail="CV file could not be retrieved")

    safe_filename = os.path.basename(cv.file_name or f"resume_{cv_id}.pdf")
    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }
    )


@router.delete("/cv/{cv_id}")
def delete_cv(
    cv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Deletes an uploaded CV file if not linked to existing analyses.
    """
    cv = db.query(CV).filter(CV.id == cv_id, CV.user_id == current_user.id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")

    linked_analyses = db.query(Analysis).filter(Analysis.cv_id == cv_id).count()
    if linked_analyses > 0:
        raise HTTPException(
            status_code=400,
            detail=f"This CV cannot be deleted because it is linked to {linked_analyses} historical analysis session(s)."
        )

    try:
        storage = get_storage_backend()
        storage.delete_file(cv.file_path)
    except Exception as e:
        logger.warning(f"Failed to delete physical CV file: {e}")

    db.delete(cv)
    db.commit()
    return {"message": "CV deleted successfully", "id": cv_id}


@router.get("/cv/sessions")
def get_past_analysis_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Retrieves past job requirement & match analysis sessions for the authenticated candidate with summary statistics.
    """
    analyses = db.query(Analysis).filter(Analysis.user_id == current_user.id).order_by(Analysis.created_at.desc()).all()
    sessions = []

    # Get latest CV text for matching if available
    latest_cv = db.query(CV).filter(CV.user_id == current_user.id).order_by(CV.uploaded_at.desc()).first()
    cv_text = ""
    latest_path = getattr(latest_cv, "file_path", None) if latest_cv else None
    if latest_path and os.path.exists(str(latest_path)):
        try:
            pdf_data = extract_pdf_text(str(latest_path))
            cv_text = pdf_data.get("text", "")
        except Exception:
            pass

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

        matched_skills = []
        missing_skills = []
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
            }, db, current_user.id, analysis_id_val)

        skills_list = combined.get("skills", [])
        total_skills_count = len(skills_list) if skills_list else len(parsed_skills)
        matched_skills_count = len([s for s in skills_list if s.get("matched") and not s.get("is_weakness")]) if skills_list else score_data.get("matched_count", 0)
        improvement_skills_count = len([s for s in skills_list if s.get("is_weakness") or not s.get("matched")]) if skills_list else score_data.get("missing_count", 0)

        score_val = float(str(a.overall_score)) if a.overall_score is not None else float(score_data.get("score", 0))

        # Readiness categorization
        if score_val >= 80:
            overall_readiness = "Advanced"
        elif score_val >= 60:
            overall_readiness = "Intermediate"
        elif score_val >= 40:
            overall_readiness = "Basic"
        else:
            overall_readiness = "Foundational"

        # Assessment status: check if any skill is assessed or complete
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
    return {"sessions": sessions}


@router.get("/cv/sessions/{analysis_id}")
def get_analysis_session_detail(
    analysis_id: int,
    force_reanalyze: bool = Query(False, description="Explicitly request reanalysis via Gemini"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Retrieves full analysis result details for a specific historical session.
    """
    analysis_record = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id).first()
    if not analysis_record:
        raise HTTPException(status_code=404, detail="Analysis session not found.")

    job_record = db.query(Job).filter(Job.id == analysis_record.job_id).first()
    cv_record = db.query(CV).filter(CV.id == analysis_record.cv_id).first()
    if not cv_record:
        cv_record = db.query(CV).filter(CV.user_id == current_user.id).order_by(CV.uploaded_at.desc()).first()

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
            # Fallback for old sessions without Gemini invocation
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
        user_id=current_user.id,
        analysis_id=analysis_record_id,
    )
    result["job_title"] = job_record.title if job_record else "Job Position"
    result["company"] = job_record.company if job_record else ""
    result["analysis_id"] = analysis_record_id
    return result





@router.post("/cv/upload")
async def upload_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Processes an uploaded CV PDF file and returns extracted text and metadata.
    Persists CV record for authenticated users.
    """
    cv_data = await process_cv(file, user_id=current_user.id)
    cv_record = CV(
        user_id=current_user.id,
        file_name=cv_data.get("filename", "Uploaded_Resume.pdf"),
        file_path=cv_data.get("file_path", "")
    )
    db.add(cv_record)
    try:
        db.commit()
        db.refresh(cv_record)
        cv_data["cv_id"] = cv_record.id
    except Exception:
        db.rollback()
        file_path = cv_data.get("file_path")
        if file_path:
            storage = get_storage_backend()
            storage.delete_file(file_path)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
        raise HTTPException(status_code=500, detail="Failed to save CV record")
    return cv_data


@router.post("/cv/analyze", response_model=CVAnalyzeResponseSchema)
@limiter.limit(RATE_LIMIT_CV_ANALYZE)
async def analyze_cv(
    request: Request,
    file: Optional[UploadFile] = File(None),
    requirements: str = Form(...),
    cv_id: Optional[int] = Form(None),
    job_title: Optional[str] = Form(None),
    company: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    user_id_query: Optional[int] = Query(None, alias="user_id"),
    include_prior_assessments: bool = Form(True),
    idempotency_key: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Analyzes an uploaded CV PDF (or saved CV via cv_id) against job skill requirements.
    Persists CV, Job, and Analysis session records for logged in candidates in an atomic transaction.
    Protects against duplicate submissions and race conditions via user-scoped idempotency keys.
    Returns matched skills, missing skills, combined assessment results, level gaps, and scores.
    """
    if user_id is not None or user_id_query is not None:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required to specify user_id")
        provided_user_id = user_id if user_id is not None else user_id_query
        if provided_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to act on behalf of this user")

    effective_user_id = current_user.id if current_user else None
    user_exists = db.query(User).filter(User.id == effective_user_id).first() if effective_user_id else None

    # Resolve idempotency key from form or headers
    req_key = (
        idempotency_key
        or request.headers.get("idempotency-key")
        or request.headers.get("x-idempotency-key")
        or request.headers.get("x-request-id")
    )
    if req_key:
        req_key = req_key.strip()

    # 1. Parse and validate requirements JSON payload
    parsed_requirements = parse_and_validate_requirements(requirements)

    # 2. File boundary & early reading for request hashing
    file_bytes: Optional[bytes] = None
    if file and file.filename:
        filename = file.filename or ""
        is_pdf_mime = file.content_type in ["application/pdf", "application/x-pdf", "binary/octet-stream"]
        is_pdf_ext = filename.lower().endswith(".pdf")
        if not (is_pdf_mime or is_pdf_ext) or (not is_pdf_ext and file.content_type not in ["application/pdf", "application/x-pdf"]):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

        limit = get_max_upload_size_bytes()
        file_bytes = await read_bounded_file(file, limit)
        try:
            await file.seek(0)
        except Exception:
            pass

    # 3. Idempotency handling for authenticated users
    idempotency_record = None
    if user_exists and req_key:
        req_hash = compute_analysis_request_hash(
            requirements=requirements,
            job_title=job_title,
            company=company,
            include_prior=include_prior_assessments,
            file_bytes=file_bytes,
            cv_id=cv_id,
        )
        idempotency_record, is_new = register_or_get_analysis_request(
            db=db,
            user_id=effective_user_id,
            idempotency_key=req_key,
            request_hash=req_hash,
        )
        if not is_new:
            # Safe retry recovery: commit already succeeded previously!
            if idempotency_record.response_json:
                try:
                    return json.loads(idempotency_record.response_json)
                except Exception:
                    pass
            if idempotency_record.analysis_id:
                try:
                    return get_analysis_session_detail(
                        analysis_id=idempotency_record.analysis_id,
                        db=db,
                        current_user=current_user
                    )
                except Exception:
                    pass

    # 4. Extract CV text: either from uploaded file OR from saved CV record
    is_new_file = False
    created_file_path: Optional[str] = None
    cv_data = None
    cv_record = None

    if file and file.filename:
        is_new_file = True
        cv_data = await process_cv(file, user_id=effective_user_id)
        created_file_path = cv_data.get("file_path")
    else:
        # Search for saved CV by cv_id or latest for effective_user_id
        if cv_id:
            if not effective_user_id:
                raise HTTPException(status_code=401, detail="Authentication required to access saved CVs")
            cv_record = db.query(CV).filter(CV.id == cv_id).first()
            if not cv_record:
                raise HTTPException(status_code=404, detail="CV not found")
            if cv_record.user_id != effective_user_id:
                raise HTTPException(status_code=403, detail="Not authorized to access this CV")
        elif effective_user_id:
            cv_record = db.query(CV).filter(CV.user_id == effective_user_id).order_by(CV.uploaded_at.desc()).first()

        cv_path_val = getattr(cv_record, "file_path", None) if cv_record else None
        if cv_path_val and os.path.exists(str(cv_path_val)):
            pdf_data = extract_pdf_text(str(cv_path_val))
            cv_data = {
                "filename": str(getattr(cv_record, "file_name", "Resume.pdf")),
                "file_path": str(cv_path_val),
                "pages": pdf_data["pages"],
                "text": pdf_data["text"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="No CV file uploaded and no saved candidate CV found. Please upload a PDF resume."
            )

    # 5. Slow AI provider calls KEPT OUTSIDE the write transaction
    try:
        cv_text = str(cv_data.get("text", "")) if cv_data else ""
        evaluated_skills = evaluate_cv_with_gemini(cv_text, parsed_requirements)
        matched_skills = [s for s in evaluated_skills if s.get("cv_match_status") == "Match"]
        missing_skills = [s for s in evaluated_skills if s.get("cv_match_status") != "Match"]
        score_data = calculate_skill_score(matched_skills, missing_skills)
    except Exception as provider_err:
        logger.error(f"Provider evaluation failed: {provider_err}")
        if is_new_file and created_file_path:
            storage = get_storage_backend()
            storage.delete_file(created_file_path)
            if os.path.exists(created_file_path):
                try:
                    os.remove(created_file_path)
                except OSError:
                    pass
        if idempotency_record:
            mark_analysis_request_failed(idempotency_record.id)
        if isinstance(provider_err, HTTPException):
            raise provider_err
        raise HTTPException(status_code=502, detail=f"AI provider evaluation failed: {provider_err}")

    # 6. ATOMIC WRITE TRANSACTION for CV, Job, Analysis, and Idempotency
    idempotency_id = idempotency_record.id if idempotency_record else None
    try:
        analysis_record: Optional[Analysis] = None
        analysis_id_val: Optional[int] = None

        if user_exists:
            if is_new_file:
                cv_record = CV(
                    user_id=effective_user_id,
                    file_name=cv_data.get("filename", "Uploaded_Resume.pdf"),
                    file_path=cv_data.get("file_path", "")
                )
                db.add(cv_record)
                db.flush()

            if cv_record is None:
                raise HTTPException(
                    status_code=500,
                    detail="Unable to associate the analysis with a saved CV record.",
                )

            title_str = job_title or "Job Position"
            company_str = company or "Target Company"
            job_record = Job(
                user_id=effective_user_id,
                title=title_str,
                company=company_str,
                description=requirements
            )
            db.add(job_record)
            db.flush()

            overall_val = score_data.get("score", 0) if score_data else 0
            analysis_record = Analysis(
                user_id=effective_user_id,
                job_id=job_record.id,
                cv_id=cv_record.id,
                overall_score=overall_val,
                raw_analysis_data=json.dumps(evaluated_skills)
            )
            db.add(analysis_record)
            db.flush()
            analysis_id_val = analysis_record.id

        cv_matching_result = {
            "filename": cv_data.get("filename"),
            "pages": cv_data.get("pages"),
            "skills": evaluated_skills,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "score_data": score_data
        }

        result = combine_cv_and_assessment(
            cv_matching_result,
            db_or_assessments=db,
            user_id=effective_user_id,
            analysis_id=analysis_id_val,
            include_prior=include_prior_assessments,
        )
        if analysis_id_val is not None:
            result["analysis_id"] = analysis_id_val

        if user_exists and idempotency_record is not None:
            idem = db.query(AnalysisRequest).filter(AnalysisRequest.id == idempotency_record.id).first()
            if idem:
                idem.status = "completed"
                idem.analysis_id = analysis_id_val
                idem.response_json = json.dumps(result)
                idem.updated_at = func.now()
                db.add(idem)

        # Commit all records atomically in ONE database transaction
        if user_exists:
            db.commit()
            db.refresh(analysis_record)
            db.refresh(job_record)
            if is_new_file and cv_record is not None:
                db.refresh(cv_record)
        else:
            if is_new_file and created_file_path:
                storage = get_storage_backend()
                storage.delete_file(created_file_path)
                if os.path.exists(created_file_path):
                    try:
                        os.remove(created_file_path)
                    except OSError:
                        pass

        return result

    except Exception as ex:
        if user_exists:
            db.rollback()
        if is_new_file and created_file_path:
            storage = get_storage_backend()
            storage.delete_file(created_file_path)
            if os.path.exists(created_file_path):
                try:
                    os.remove(created_file_path)
                except OSError:
                    pass
        if idempotency_id:
            mark_analysis_request_failed(idempotency_id)
        if isinstance(ex, HTTPException):
            raise ex
        raise HTTPException(status_code=500, detail=f"Database write transaction failed: {ex}")
