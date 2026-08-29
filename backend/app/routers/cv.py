import json
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.cv_service import process_cv
from app.services.matching_service import match_skills_in_text
from app.services.scoring_service import calculate_skill_score
from app.services.skill_analysis_service import combine_cv_and_assessment
from app.schemas.cv import CVAnalyzeResponseSchema


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


@router.post("/cv/upload")
async def upload_cv(file: UploadFile = File(...)):
    """
    Processes an uploaded CV PDF file and returns extracted text and metadata.
    """
    return await process_cv(file)


@router.post("/cv/analyze", response_model=CVAnalyzeResponseSchema)
async def analyze_cv(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    user_id: Optional[int] = Form(None),
    user_id_query: Optional[int] = Query(None, alias="user_id"),
    db: Session = Depends(get_db)
):
    """
    Analyzes an uploaded CV PDF against job skill requirements.
    Returns matched skills, missing skills, combined assessment results, level gaps, and scores.
    Preserves job required level fields without candidate level prediction.
    """
    # 1. Parse and validate requirements JSON payload
    parsed_requirements = parse_and_validate_requirements(requirements)

    # 2. Extract text from uploaded PDF using existing cv_service
    cv_data = await process_cv(file)
    cv_text = cv_data.get("text", "")

    # 3. Match required skills against CV text using existing matching_service
    matched_skills, missing_skills = match_skills_in_text(cv_text, parsed_requirements)

    # 4. Calculate skill score breakdown
    score_data = calculate_skill_score(matched_skills, missing_skills)

    # 5. Build raw matching result
    cv_matching_result = {
        "filename": cv_data.get("filename"),
        "pages": cv_data.get("pages"),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score_data": score_data
    }

    # 6. Combine CV matching with completed PostgreSQL assessment results
    effective_user_id = user_id if user_id is not None else user_id_query
    return combine_cv_and_assessment(cv_matching_result, db_or_assessments=db, user_id=effective_user_id)