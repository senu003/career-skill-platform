from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import AssessmentAttempt
from app.services.skill_analysis_service import extract_assessment_scores, calculate_level_gap, LEVEL_MAP
from app.services.weakness_service import calculate_weakness
from app.services.recommendation_service import generate_recommendation

def get_candidate_history(db: Session, user_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieves and computes the longitudinal outcome history for a given candidate,
    grouped by skill.
    """
    if user_id is None:
        return {}

    attempts = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.completed_at.isnot(None),
            AssessmentAttempt.assessed_level.isnot(None)
        )
        .order_by(AssessmentAttempt.skill, AssessmentAttempt.completed_at.asc(), AssessmentAttempt.id.asc())
        .all()
    )

    history_by_skill = {}
    
    for attempt in attempts:
        skill = attempt.skill.lower().strip()
        if skill not in history_by_skill:
            history_by_skill[skill] = []
            
        scores = extract_assessment_scores(db, {"attempt_id": attempt.id})
        total_score = scores.get("total_score") if scores else None
        
        level_gap = calculate_level_gap(attempt.required_level, attempt.assessed_level)
        weakness_info = calculate_weakness(level_gap, total_score)
        
        rec_info = generate_recommendation(
            skill=attempt.skill,
            required_level=attempt.required_level,
            assessed_level=attempt.assessed_level,
            level_gap=level_gap,
            total_score=total_score,
            is_weakness=weakness_info["is_weakness"],
            weakness_reason=weakness_info["weakness_reason"]
        )

        obs = {
            "attempt_id": attempt.id,
            "skill": attempt.skill,
            "required_level": attempt.required_level,
            "assessed_level": attempt.assessed_level,
            "basic_score": scores.get("basic_score") if scores else None,
            "intermediate_score": scores.get("intermediate_score") if scores else None,
            "advanced_score": scores.get("advanced_score") if scores else None,
            "total_score": total_score,
            "level_gap": level_gap,
            "is_weakness": weakness_info["is_weakness"],
            "weakness_reason": weakness_info["weakness_reason"],
            "priority": rec_info["priority"],
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
            "outcome": None
        }
        
        history_by_skill[skill].append(obs)
        
    # Now compute longitudinal outcomes
    for skill, obs_list in history_by_skill.items():
        for i in range(1, len(obs_list)):
            prev = obs_list[i-1]
            curr = obs_list[i]
            
            score_change = None
            if curr["total_score"] is not None and prev["total_score"] is not None:
                score_change = round(curr["total_score"] - prev["total_score"], 4)
                
            level_change = None
            if curr["assessed_level"] and prev["assessed_level"]:
                prev_lvl = LEVEL_MAP.get(prev["assessed_level"].lower(), 0)
                curr_lvl = LEVEL_MAP.get(curr["assessed_level"].lower(), 0)
                level_change = curr_lvl - prev_lvl
                
            improved = False
            declined = False
            persistent_weakness = False
            
            if level_change is not None and score_change is not None:
                if level_change > 0 or (level_change == 0 and score_change > 0):
                    improved = True
                elif level_change < 0 or (level_change == 0 and score_change < 0):
                    declined = True
                    
            if prev["is_weakness"] and curr["is_weakness"]:
                persistent_weakness = True
                
            curr["outcome"] = {
                "score_change": score_change,
                "level_change": level_change,
                "improved": improved,
                "declined": declined,
                "persistent_weakness": persistent_weakness
            }

    return history_by_skill


from datetime import datetime
from app.services.matching_service import get_skill_variants
from app.ml.longitudinal_predictor import predict_improvement_probability


def get_previous_attempt_t0_features(
    db: Session,
    user_id: Optional[int],
    skill: str,
    current_attempt_id: Optional[int] = None,
    cv_matched: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Retrieves t0 feature dict from the candidate's previous completed assessment attempt for a given skill.
    Returns None if user_id is None, skill is empty, or candidate has <= 1 attempt (insufficient history).
    """
    if user_id is None or not skill or not skill.strip():
        return None

    skill_clean = skill.strip()
    variants = get_skill_variants(skill_clean)
    variants_lower = [v.lower() for v in variants]

    query = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.completed_at.isnot(None),
            AssessmentAttempt.assessed_level.isnot(None)
        )
    )

    if current_attempt_id is not None:
        query = query.filter(AssessmentAttempt.id != current_attempt_id)

    query = query.order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())
    completed_attempts = query.all()

    # Find matched attempt by skill name / variants
    matched_previous = None
    for attempt in completed_attempts:
        if attempt.skill.strip().lower() in variants_lower or skill_clean.lower() == attempt.skill.strip().lower():
            matched_previous = attempt
            break

    if not matched_previous:
        return None

    scores = extract_assessment_scores(db, {"attempt_id": matched_previous.id})
    if not scores:
        return None

    level_gap = calculate_level_gap(matched_previous.required_level, matched_previous.assessed_level)
    weakness_info = calculate_weakness(level_gap, scores.get("total_score"))

    rec_info = generate_recommendation(
        skill=matched_previous.skill,
        required_level=matched_previous.required_level,
        assessed_level=matched_previous.assessed_level,
        level_gap=level_gap,
        total_score=scores.get("total_score"),
        is_weakness=weakness_info["is_weakness"],
        weakness_reason=weakness_info["weakness_reason"]
    )

    days_between = 30.0
    if matched_previous.completed_at:
        now_dt = datetime.now()
        days_between = max(0.0, (now_dt - matched_previous.completed_at).total_seconds() / (24 * 3600.0))

    return {
        "previous_assessed_level": matched_previous.assessed_level,
        "required_level": matched_previous.required_level,
        "previous_priority": rec_info.get("priority", "Medium"),
        "previous_total_score": scores.get("total_score"),
        "previous_level_gap": level_gap if level_gap is not None else 0,
        "cv_match_score": 1.0 if cv_matched else 0.0,
        "cv_matched": cv_matched,
        "previous_is_weakness": 1 if weakness_info.get("is_weakness") else 0,
        "days_between_attempts": days_between,
        "previous_basic_score": scores.get("basic_score"),
        "previous_intermediate_score": scores.get("intermediate_score"),
        "previous_advanced_score": scores.get("advanced_score"),
    }


def predict_skill_improvement_from_history(
    db: Session,
    user_id: Optional[int],
    skill: str,
    current_attempt_id: Optional[int] = None,
    cv_matched: bool = True
) -> Optional[float]:
    """
    Predicts improvement probability using candidate's previous assessment attempt history.
    Returns None when history is insufficient (0 previous completed attempts).
    """
    t0_features = get_previous_attempt_t0_features(
        db=db,
        user_id=user_id,
        skill=skill,
        current_attempt_id=current_attempt_id,
        cv_matched=cv_matched
    )
    if not t0_features:
        return None

    return predict_improvement_probability(t0_features)

