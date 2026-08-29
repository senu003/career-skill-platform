from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AssessmentAttempt
from app.schemas.assessment import (
    StartAssessmentRequest,
    StartAssessmentResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    AttemptStatusResponse,
    CompleteAssessmentResponse
)
from app.schemas.skill_analysis import AssessmentResultSchema
from app.services import assessment_service, skill_analysis_service

router = APIRouter(
    prefix="/assessment",
    tags=["Assessment"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/start", response_model=StartAssessmentResponse, status_code=status.HTTP_201_CREATED)
def start_assessment(payload: StartAssessmentRequest, db: Session = Depends(get_db)):
    res = assessment_service.start_assessment(
        db=db,
        skill=payload.skill,
        required_level=payload.required_level,
        user_id=payload.user_id
    )
    return res


@router.post("/answer", response_model=SubmitAnswerResponse)
def submit_answer(payload: SubmitAnswerRequest, db: Session = Depends(get_db)):
    res = assessment_service.submit_answer(
        db=db,
        attempt_id=payload.attempt_id,
        question_id=payload.question_id,
        selected_answer=payload.selected_answer
    )
    return res


@router.get("/result/{skill}", response_model=AssessmentResultSchema)
def get_assessment_result_by_skill(
    skill: str,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    res = skill_analysis_service.get_assessment_result_for_skill(db=db, skill=skill, user_id=user_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed assessment found for skill '{skill}'."
        )
    return res


@router.get("/{attempt_id}", response_model=AttemptStatusResponse)
def get_assessment_status(attempt_id: int, db: Session = Depends(get_db)):
    res = assessment_service.get_attempt_details(db=db, attempt_id=attempt_id)
    return res


@router.get("/{attempt_id}/result", response_model=AssessmentResultSchema)
def get_assessment_result_by_attempt(attempt_id: int, db: Session = Depends(get_db)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )
    if attempt.completed_at is None or attempt.assessed_level is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assessment attempt {attempt_id} is not yet completed."
        )
    gap = skill_analysis_service.calculate_level_gap(attempt.required_level, attempt.assessed_level)
    return {
        "attempt_id": attempt.id,
        "skill": attempt.skill,
        "required_level": attempt.required_level,
        "assessed_level": attempt.assessed_level,
        "level_gap": gap
    }


@router.post("/{attempt_id}/complete", response_model=CompleteAssessmentResponse)
def complete_assessment(attempt_id: int, db: Session = Depends(get_db)):
    res = assessment_service.complete_assessment(db=db, attempt_id=attempt_id)
    return res

