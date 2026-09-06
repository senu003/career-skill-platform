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
from app.auth_deps import get_current_user_required, get_current_user, User

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


@router.get("/supported-skills")
def get_supported_skills():
    return {"supported_skills": assessment_service.get_supported_skills_list()}


@router.post("/start", response_model=StartAssessmentResponse, status_code=status.HTTP_201_CREATED)
def start_assessment(
    payload: StartAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    effective_user_id = payload.user_id if payload.user_id is not None else (current_user.id if current_user else None)
    res = assessment_service.start_assessment(
        db=db,
        skill=payload.skill,
        required_level=payload.required_level,
        user_id=effective_user_id
    )
    return res


@router.post("/answer", response_model=SubmitAnswerResponse)
def submit_answer(payload: SubmitAnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == payload.attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")

    res = assessment_service.submit_answer(
        db=db,
        attempt_id=payload.attempt_id,
        question_id=payload.question_id,
        selected_answer=payload.selected_answer,
        time_taken=payload.time_taken
    )
    return res


@router.get("/result/{skill}", response_model=AssessmentResultSchema)
def get_assessment_result_by_skill(
    skill: str,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    effective_user_id = user_id if user_id is not None else (current_user.id if current_user else None)
    res = skill_analysis_service.get_assessment_result_for_skill(db=db, skill=skill, user_id=effective_user_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed assessment found for skill '{skill}'."
        )
        
    scores = skill_analysis_service.extract_assessment_scores(db, res)
    total_score = scores.get("total_score") if scores else None
    res["total_score"] = total_score
    
    weakness_info = skill_analysis_service.calculate_weakness(level_gap=res["level_gap"], total_score=total_score)
    res["is_weakness"] = weakness_info["is_weakness"]
    res["weakness_reason"] = weakness_info["weakness_reason"]
    
    rec_info = skill_analysis_service.generate_recommendation(
        skill=res["skill"],
        required_level=res["required_level"],
        assessed_level=res["assessed_level"],
        level_gap=res["level_gap"],
        total_score=total_score,
        is_weakness=res["is_weakness"],
        weakness_reason=res["weakness_reason"]
    )
    res["priority"] = rec_info["priority"]
    res["recommendation"] = rec_info["recommendation"]
    res["recommendation_reason"] = rec_info["reason"]
    
    return res


@router.get("/{attempt_id}", response_model=AttemptStatusResponse)
def get_assessment_status(attempt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")

    res = assessment_service.get_attempt_details(db=db, attempt_id=attempt_id)
    return res


@router.get("/{attempt_id}/result", response_model=AssessmentResultSchema)
def get_assessment_result_by_attempt(attempt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")
    
    if attempt.completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assessment attempt {attempt_id} is not yet completed."
        )
    scores = skill_analysis_service.extract_assessment_scores(db, {"attempt_id": attempt.id})
    total_score = scores.get("total_score") if scores else None

    assessed_lvl = attempt.assessed_level
    if not assessed_lvl and scores:
        assessed_lvl = skill_analysis_service.generate_ml_prediction(
            matched=True,
            required_level=attempt.required_level,
            importance="required",
            scores=scores
        )
        if assessed_lvl and attempt.assessed_level != assessed_lvl:
            attempt.assessed_level = assessed_lvl
            db.commit()

    gap = skill_analysis_service.calculate_level_gap(attempt.required_level, assessed_lvl)
    weakness_info = skill_analysis_service.calculate_weakness(level_gap=gap, total_score=total_score)
    rec_info = skill_analysis_service.generate_recommendation(
        skill=attempt.skill,
        required_level=attempt.required_level,
        assessed_level=assessed_lvl,
        level_gap=gap,
        total_score=total_score,
        is_weakness=weakness_info["is_weakness"],
        weakness_reason=weakness_info["weakness_reason"]
    )

    from app.services.longitudinal_service import predict_skill_improvement_from_history
    improvement_prob = predict_skill_improvement_from_history(
        db=db,
        user_id=attempt.user_id,
        skill=attempt.skill,
        current_attempt_id=attempt.id
    )

    model1_rec, model1_conf = skill_analysis_service.generate_model1_evaluator_output(
        required_level=attempt.required_level,
        assessed_level=assessed_lvl,
        scores=scores,
        cv_level=attempt.cv_level
    )

    return {
        "attempt_id": attempt.id,
        "skill": attempt.skill,
        "required_level": attempt.required_level,
        "assessed_level": assessed_lvl,
        "level_gap": gap,
        "total_score": total_score,
        "is_weakness": weakness_info["is_weakness"],
        "weakness_reason": weakness_info["weakness_reason"],
        "priority": rec_info["priority"],
        "recommendation": rec_info["recommendation"],
        "recommendation_reason": rec_info["reason"],
        "skill_recommendation": model1_rec,
        "recommendation_confidence": model1_conf,
        "improvement_probability": improvement_prob,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None
    }


@router.post("/{attempt_id}/complete", response_model=CompleteAssessmentResponse)
def complete_assessment(attempt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")

    res = assessment_service.complete_assessment(db=db, attempt_id=attempt_id)
    return res

from app.schemas.assessment import AssessmentHistoryObservation
from typing import Dict, List
from app.services import longitudinal_service

@router.get("/history/me", response_model=Dict[str, List[AssessmentHistoryObservation]])
def get_my_candidate_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    res = longitudinal_service.get_candidate_history(db=db, user_id=current_user.id)
    return res

@router.get("/history/{user_id}", response_model=Dict[str, List[AssessmentHistoryObservation]])
def get_candidate_history(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required to fetch longitudinal history."
        )
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this history")
        
    res = longitudinal_service.get_candidate_history(db=db, user_id=user_id)
    return res


