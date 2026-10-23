import json
import os
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.cv_service import process_cv, extract_pdf_text
from app.services.requirement_service import extract_requirements, evaluate_cv_with_gemini
from app.services.matching_service import match_skills_in_text
from app.services.scoring_service import calculate_skill_score
from app.services.skill_analysis_service import combine_cv_and_assessment
from app.schemas.cv import CVAnalyzeResponseSchema
from app.auth_deps import get_current_user, get_current_user_required, User
from app.models import CV, Job, Analysis


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    return {
        "has_cv": True,
        "cv": {
            "id": cv_record.id,
            "file_name": cv_record.file_name,
            "uploaded_at": cv_record.uploaded_at.isoformat() if cv_record.uploaded_at else None
        }
    }


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
    if latest_cv and latest_cv.file_path and os.path.exists(latest_cv.file_path):
        try:
            pdf_data = extract_pdf_text(latest_cv.file_path)
            cv_text = pdf_data.get("text", "")
        except Exception:
            pass

    for a in analyses:
        job = db.query(Job).filter(Job.id == a.job_id).first()
        cv_obj = db.query(CV).filter(CV.id == a.cv_id).first()
        if not cv_obj:
            cv_obj = latest_cv

        parsed_skills = []
        if job and job.description:
            try:
                parsed_skills = json.loads(job.description)
            except Exception:
                pass

        matched_skills = []
        missing_skills = []
        score_data = {"score": 0, "matched_count": 0, "missing_count": 0, "total_skills": 0}
        combined = {"skills": []}

        if parsed_skills:
            if a.raw_analysis_data:
                try:
                    evaluated_skills = json.loads(a.raw_analysis_data)
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
            combined = combine_cv_and_assessment({
                "skills": evaluated_skills,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "score_data": score_data
            }, db, current_user.id, a.id)

        skills_list = combined.get("skills", [])
        total_skills_count = len(skills_list) if skills_list else len(parsed_skills)
        matched_skills_count = len([s for s in skills_list if s.get("matched") and not s.get("is_weakness")]) if skills_list else score_data.get("matched_count", 0)
        improvement_skills_count = len([s for s in skills_list if s.get("is_weakness") or not s.get("matched")]) if skills_list else score_data.get("missing_count", 0)

        score_val = float(a.overall_score) if a.overall_score is not None else float(score_data.get("score", 0))

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
            "status_badge": "Analysis Complete",
            "created_at": a.created_at.isoformat() if a.created_at else None
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

    parsed_requirements = parse_and_validate_requirements(job_record.description) if job_record and job_record.description else []

    cv_text = ""
    if cv_record and cv_record.file_path and os.path.exists(cv_record.file_path):
        pdf_data = extract_pdf_text(cv_record.file_path)
        cv_text = pdf_data.get("text", "")

    if analysis_record.raw_analysis_data and not force_reanalyze:
        evaluated_skills = json.loads(analysis_record.raw_analysis_data)
    else:
        if not force_reanalyze and not analysis_record.raw_analysis_data:
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
                analysis_record.raw_analysis_data = json.dumps(evaluated_skills)
                db.commit()

    matched_skills = [s for s in evaluated_skills if s.get("cv_match_status") == "Match"]
    missing_skills = [s for s in evaluated_skills if s.get("cv_match_status") != "Match"]
    score_data = calculate_skill_score(matched_skills, missing_skills)

    cv_matching_result = {
        "filename": cv_record.file_name if cv_record else "Resume.pdf",
        "pages": 1,
        "skills": evaluated_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score_data": score_data
    }

    result = combine_cv_and_assessment(
        cv_matching_result,
        db_or_assessments=db,
        user_id=current_user.id,
        analysis_id=analysis_record.id,
    )
    result["job_title"] = job_record.title if job_record else "Job Position"
    result["company"] = job_record.company if job_record else ""
    result["analysis_id"] = analysis_record.id
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
    cv_data = await process_cv(file)
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
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail="Failed to save CV record")
    return cv_data


@router.post("/cv/analyze", response_model=CVAnalyzeResponseSchema)
async def analyze_cv(
    file: Optional[UploadFile] = File(None),
    requirements: str = Form(...),
    cv_id: Optional[int] = Form(None),
    job_title: Optional[str] = Form(None),
    company: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    user_id_query: Optional[int] = Query(None, alias="user_id"),
    include_prior_assessments: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Analyzes an uploaded CV PDF (or saved CV via cv_id) against job skill requirements.
    Persists CV, Job, and Analysis session records for logged in candidates.
    Returns matched skills, missing skills, combined assessment results, level gaps, and scores.
    """
    if user_id is not None or user_id_query is not None:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required to specify user_id")
        provided_user_id = user_id if user_id is not None else user_id_query
        if provided_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to act on behalf of this user")
            
    effective_user_id = current_user.id if current_user else None

    # 1. Parse and validate requirements JSON payload
    parsed_requirements = parse_and_validate_requirements(requirements)

    cv_data = None
    cv_record = None

    user_exists = db.query(User).filter(User.id == effective_user_id).first() if effective_user_id else None

    # 2. Extract CV text: either from uploaded file OR from saved CV record
    if file and file.filename:
        cv_data = await process_cv(file)
        if user_exists:
            cv_record = CV(
                user_id=effective_user_id,
                file_name=cv_data.get("filename", "Uploaded_Resume.pdf"),
                file_path=cv_data.get("file_path", "")
            )
            db.add(cv_record)
            try:
                db.commit()
                db.refresh(cv_record)
            except Exception:
                db.rollback()
                if cv_data.get("file_path") and os.path.exists(cv_data["file_path"]):
                    try:
                        os.remove(cv_data["file_path"])
                    except OSError:
                        pass
                raise HTTPException(status_code=500, detail="Failed to save CV record")
        else:
            # Clean up temporary uploaded file for unauthenticated users
            if cv_data.get("file_path") and os.path.exists(cv_data["file_path"]):
                try:
                    os.remove(cv_data["file_path"])
                except OSError:
                    pass
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

        if cv_record and cv_record.file_path and os.path.exists(cv_record.file_path):
            pdf_data = extract_pdf_text(cv_record.file_path)
            cv_data = {
                "filename": cv_record.file_name,
                "file_path": cv_record.file_path,
                "pages": pdf_data["pages"],
                "text": pdf_data["text"]
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="No CV file uploaded and no saved candidate CV found. Please upload a PDF resume."
            )

    cv_text = cv_data.get("text", "")

    # 3. Evaluate candidate CV against requirements using Gemini
    evaluated_skills = evaluate_cv_with_gemini(cv_text, parsed_requirements)
    matched_skills = [s for s in evaluated_skills if s.get("cv_match_status") == "Match"]
    missing_skills = [s for s in evaluated_skills if s.get("cv_match_status") != "Match"]

    # 4. Calculate skill score breakdown
    score_data = calculate_skill_score(matched_skills, missing_skills)

    # 5. Save Job & Analysis session records for logged-in user
    if user_exists:
        title_str = job_title or "Job Position"
        company_str = company or "Target Company"
        job_record = Job(
            user_id=effective_user_id,
            title=title_str,
            company=company_str,
            description=requirements
        )
        db.add(job_record)
        db.commit()
        db.refresh(job_record)

        if cv_record is None:
            raise HTTPException(
                status_code=500,
                detail="Unable to associate the analysis with a saved CV record.",
            )

        overall_val = score_data.get("score", 0) if score_data else 0
        analysis_record = Analysis(
            user_id=effective_user_id,
            job_id=job_record.id,
            cv_id=cv_record.id if cv_record else None,
            overall_score=overall_val,
            raw_analysis_data=json.dumps(evaluated_skills)
        )
        db.add(analysis_record)
        db.commit()

    # 6. Build raw matching result
    cv_matching_result = {
        "filename": cv_data.get("filename"),
        "pages": cv_data.get("pages"),
        "skills": evaluated_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score_data": score_data
    }

    # 7. Combine CV matching with completed assessment results
    result = combine_cv_and_assessment(
        cv_matching_result,
        db_or_assessments=db,
        user_id=effective_user_id,
        analysis_id=analysis_record.id if user_exists else None,
        include_prior=include_prior_assessments,
    )
    if user_exists:
        result["analysis_id"] = analysis_record.id
    return result