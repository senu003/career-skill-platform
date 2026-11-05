from typing import Optional, Dict, List, cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import AssessmentAttempt, Analysis
from app.schemas.assessment import (
    StartAssessmentRequest,
    StartAssessmentResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    AttemptStatusResponse,
    CompleteAssessmentResponse,
    AssessmentHistoryObservation,
    AssessmentReviewResponse,
    TargetedRevisionResponse,
    InterviewPrepSummaryResponse,
    SkillAnalysisDetailResponse,
    PersonalizedNextStepsResponse
)
from app.schemas.skill_analysis import AssessmentResultSchema
from app.services import assessment_service, skill_analysis_service, longitudinal_service
from app.services.assessment_review_service import get_assessment_review, get_user_weakness_analysis
from app.services.interview_prep_service import (
    get_interview_prep_summary,
    get_skill_analysis_detail,
    get_personalized_next_steps,
)
from app.auth_deps import get_current_user_required, get_current_user, User

router = APIRouter(
    prefix="/assessment",
    tags=["Assessment"]
)




@router.get("/supported-skills")
def get_supported_skills():
    return {"supported_skills": assessment_service.get_supported_skills_list()}


@router.post("/start", response_model=StartAssessmentResponse, status_code=status.HTTP_201_CREATED)
def start_assessment(
    payload: StartAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    if payload.user_id is not None:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to specify user_id")
        if payload.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to start assessment for this user")

    if payload.analysis_id is not None:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to specify analysis_id")
        analysis = db.query(Analysis).filter(
            Analysis.id == payload.analysis_id,
            Analysis.user_id == current_user.id,
        ).first()
        if not analysis:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis session not found")
            
    effective_user_id: Optional[int] = cast(int, current_user.id) if current_user else None
    res = assessment_service.start_assessment(
        db=db,
        skill=payload.skill,
        required_level=payload.required_level,
        user_id=effective_user_id,
        analysis_id=payload.analysis_id,
        topic=payload.topic,
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
    analysis_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    if user_id is not None:
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required to specify user_id")
        if user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this user's result")
            
    effective_user_id: Optional[int] = cast(int, current_user.id) if current_user else None
    res = skill_analysis_service.get_assessment_result_for_skill(
        db=db,
        skill=skill,
        user_id=effective_user_id,
        analysis_id=analysis_id,
    )
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


@router.get("/history/me", response_model=Dict[str, List[AssessmentHistoryObservation]])
def get_my_candidate_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    res = longitudinal_service.get_candidate_history(db=db, user_id=cast(int, current_user.id))
    return res

@router.get("/history/{user_id}", response_model=Dict[str, List[AssessmentHistoryObservation]])
def get_candidate_history(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this history")
        
    res = longitudinal_service.get_candidate_history(db=db, user_id=user_id)
    return res


@router.get("/revision/weaknesses", response_model=TargetedRevisionResponse)
def get_user_revision_weaknesses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Returns rule-based topic accuracy, identified weakness topics, and targeted revision recommendations.
    """
    return get_user_weakness_analysis(db=db, user_id=cast(int, current_user.id))


@router.get("/interview-prep/summary", response_model=InterviewPrepSummaryResponse)
def get_interview_prep_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Returns Interview Prep Hub overview across all supported skills,
    including latest scores, trends, overall statistics, and key takeaways.
    """
    return get_interview_prep_summary(db=db, user_id=cast(int, current_user.id))


@router.get("/interview-prep/skill/{skill}", response_model=SkillAnalysisDetailResponse)
def get_skill_prep_analysis(
    skill: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Returns individual skill analysis with chronological score progression,
    attempt stats, performance trend explanation, and past attempts.
    """
    return get_skill_analysis_detail(db=db, user_id=cast(int, current_user.id), skill_input=skill)


@router.get("/interview-prep/next-steps", response_model=PersonalizedNextStepsResponse)
def get_prep_next_steps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Returns personalized next steps prioritizing repeated mistakes and persistent error topics.
    """
    return get_personalized_next_steps(db=db, user_id=cast(int, current_user.id))




@router.get("/{attempt_id}", response_model=AttemptStatusResponse)
def get_assessment_status(attempt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")

    res = assessment_service.get_attempt_details(db=db, attempt_id=attempt_id)
    return res


@router.get("/{attempt_id}/review", response_model=AssessmentReviewResponse)
def get_attempt_review(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_required)
):
    """
    Returns question-by-question review with selected answers, correct answers,
    explanations, misconceptions, and interview tips.
    """
    return get_assessment_review(db=db, attempt_id=attempt_id, current_user_id=cast(int, current_user.id))



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
    return skill_analysis_service.build_assessment_attempt_result(db=db, attempt=attempt)



@router.post("/{attempt_id}/complete", response_model=CompleteAssessmentResponse)
def complete_assessment(attempt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_required)):
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this attempt")

    res = assessment_service.complete_assessment(db=db, attempt_id=attempt_id)
    return res

