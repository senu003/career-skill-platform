from typing import Optional, Dict, Any, List, Union, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import AssessmentAttempt, AssessmentAnswer, AssessmentQuestion
from app.services.matching_service import get_skill_variants
from app.ml.predict import SkillLevelPredictor
from app.services.weakness_service import calculate_weakness
from app.services.recommendation_service import generate_recommendation

LEVEL_MAP: Dict[str, int] = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3
}


def calculate_level_gap(required_level: Optional[str], assessed_level: Optional[str]) -> Optional[int]:
    """
    Calculates the level gap between required level and assessed level.
    Level order: basic = 1, intermediate = 2, advanced = 3.

    Rule: Do not treat a higher assessed level as a negative gap (returns 0).
    Rule: If either level is null, returns None for level_gap.
    """
    if not required_level or not assessed_level:
        return None

    req_clean = required_level.strip().lower()
    ass_clean = assessed_level.strip().lower()

    if req_clean not in LEVEL_MAP or ass_clean not in LEVEL_MAP:
        return None

    req_val = LEVEL_MAP[req_clean]
    ass_val = LEVEL_MAP[ass_clean]

    return max(0, req_val - ass_val)


def get_assessment_result_for_skill(
    db: Session,
    skill: str,
    user_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieves the latest completed assessment result for a given skill (and optional user_id).
    Returns dict with attempt_id, skill, required_level, assessed_level, and level_gap.
    """
    if not skill or not skill.strip():
        return None

    skill_clean = skill.strip()
    variants = get_skill_variants(skill_clean)
    variants_lower = [v.lower() for v in variants]

    if user_id is None:
        return None

    query = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.completed_at.isnot(None),
            AssessmentAttempt.user_id == user_id
        )
    )

    # Order by completed_at desc, id desc to get latest
    query = query.order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())

    attempts = query.all()

    # Find attempt matching skill name or any variant
    matched_attempt = None
    for attempt in attempts:
        attempt_skill_lower = attempt.skill.strip().lower()
        if attempt_skill_lower in variants_lower or skill_clean.lower() == attempt_skill_lower:
            matched_attempt = attempt
            break

    if not matched_attempt:
        return None

    gap = calculate_level_gap(matched_attempt.required_level, matched_attempt.assessed_level)

    from app.services.longitudinal_service import predict_skill_improvement_from_history
    improvement_prob = predict_skill_improvement_from_history(
        db=db,
        user_id=user_id,
        skill=matched_attempt.skill,
        current_attempt_id=matched_attempt.id
    )

    scores = extract_assessment_scores(db, {"attempt_id": matched_attempt.id})

    assessed_lvl = matched_attempt.assessed_level
    if not assessed_lvl and scores:
        assessed_lvl = generate_ml_prediction(
            matched=True,
            required_level=matched_attempt.required_level,
            importance="required",
            scores=scores
        )
        if assessed_lvl and matched_attempt.assessed_level != assessed_lvl:
            matched_attempt.assessed_level = assessed_lvl
            db.commit()

    gap = calculate_level_gap(matched_attempt.required_level, assessed_lvl)

    from app.services.longitudinal_service import predict_skill_improvement_from_history
    improvement_prob = predict_skill_improvement_from_history(
        db=db,
        user_id=user_id,
        skill=matched_attempt.skill,
        current_attempt_id=matched_attempt.id
    )

    model1_rec, model1_conf = generate_model1_evaluator_output(
        required_level=matched_attempt.required_level,
        assessed_level=assessed_lvl,
        scores=scores,
        cv_level=matched_attempt.cv_level
    )

    return {
        "attempt_id": matched_attempt.id,
        "skill": matched_attempt.skill,
        "required_level": matched_attempt.required_level,
        "assessed_level": assessed_lvl,
        "level_gap": gap,
        "skill_recommendation": model1_rec,
        "recommendation_confidence": model1_conf,
        "improvement_probability": improvement_prob
    }


def extract_assessment_scores(
    db_or_assessments: Optional[Union[Session, Dict[str, Any], List[Dict[str, Any]]]],
    assessment_data: Optional[Dict[str, Any]]
) -> Optional[Dict[str, float]]:
    """
    Extracts or calculates basic_score, intermediate_score, advanced_score, and total_score from assessment data.
    Returns None if assessment information is insufficient.
    """
    if not assessment_data:
        return None

    # Check if scores are directly provided in assessment_data dictionary
    if (
        "basic_score" in assessment_data
        and "intermediate_score" in assessment_data
        and "advanced_score" in assessment_data
    ):
        b_s = float(assessment_data["basic_score"])
        i_s = float(assessment_data["intermediate_score"])
        a_s = float(assessment_data["advanced_score"])
        t_s = float(assessment_data.get("total_score", round(min(1.0, max(0.0, (0.35 * b_s) + (0.40 * i_s) + (0.25 * a_s))), 4)))
        return {
            "basic_score": b_s,
            "intermediate_score": i_s,
            "advanced_score": a_s,
            "total_score": t_s
        }

    # If DB session and attempt_id are present, calculate scores from AssessmentAnswers
    if isinstance(db_or_assessments, Session) and "attempt_id" in assessment_data:
        attempt_id = assessment_data["attempt_id"]
        answers = (
            db_or_assessments.query(AssessmentAnswer)
            .join(AssessmentQuestion, AssessmentAnswer.question_id == AssessmentQuestion.id)
            .filter(AssessmentAnswer.attempt_id == attempt_id)
            .all()
        )

        if not answers:
            return None

        level_counts = {
            "basic": {"correct": 0, "total": 0},
            "intermediate": {"correct": 0, "total": 0},
            "advanced": {"correct": 0, "total": 0}
        }

        for ans in answers:
            lvl = ans.question_obj.level.lower() if ans.question_obj and ans.question_obj.level else None
            if lvl in level_counts:
                level_counts[lvl]["total"] += 1
                if ans.is_correct:
                    level_counts[lvl]["correct"] += 1

        total_ans = sum(c["total"] for c in level_counts.values())
        if total_ans == 0:
            return None

        b_score = round(level_counts["basic"]["correct"] / 5.0, 4) if level_counts["basic"]["total"] > 0 else 0.0
        i_score = round(level_counts["intermediate"]["correct"] / 5.0, 4) if level_counts["intermediate"]["total"] > 0 else 0.0
        a_score = round(level_counts["advanced"]["correct"] / 5.0, 4) if level_counts["advanced"]["total"] > 0 else 0.0
        t_score = round(min(1.0, max(0.0, (0.35 * b_score) + (0.40 * i_score) + (0.25 * a_score))), 4)

        return {
            "basic_score": b_score,
            "intermediate_score": i_score,
            "advanced_score": a_score,
            "total_score": t_score
        }

    return None


def generate_ml_prediction(
    matched: bool,
    required_level: str,
    importance: str,
    scores: Optional[Dict[str, float]]
) -> Optional[str]:
    """
    Generates ML prediction for a skill based on CV matching and assessment scores.
    Returns None if scores are insufficient or missing.
    """
    if not scores:
        return None

    try:
        predictor = SkillLevelPredictor()
        feature_dict = {
            "cv_matched": 1 if matched else 0,
            "required_level": required_level.lower().strip(),
            "importance": importance.lower().strip() if importance else "required",
            "basic_score": scores["basic_score"],
            "intermediate_score": scores["intermediate_score"],
            "advanced_score": scores["advanced_score"],
            "total_score": scores["total_score"]
        }
        res = predictor.predict_single(feature_dict)
        return res.get("predicted_level")
    except Exception:
        return None


def generate_model1_evaluator_output(
    required_level: str,
    assessed_level: Optional[str],
    scores: Optional[Dict[str, float]],
    cv_level: Optional[str] = None,
    avg_time_per_question: Optional[float] = None,
    attempt_count: int = 1,
    previous_best_score: Optional[float] = None
) -> Tuple[Optional[str], Optional[float]]:
    """
    Invokes Model 1 Skill Evaluator ML predictor and returns (skill_recommendation, recommendation_confidence).
    Returns (None, None) if assessment data is not completed.
    """
    if not assessed_level and not scores:
        return None, None

    try:
        from app.ml.predict_weakness import predict_skill_evaluator
        feature_input = {
            "jd_required_level": required_level,
            "cv_parsed_level": cv_level,
            "assessed_level": assessed_level,
            "basic_score": scores.get("basic_score", 0.0) if scores else 0.0,
            "intermediate_score": scores.get("intermediate_score", 0.0) if scores else 0.0,
            "advanced_score": scores.get("advanced_score", 0.0) if scores else 0.0,
            "assessment_score": scores.get("total_score", 0.0) if scores else 0.0,
            "avg_time_per_question": avg_time_per_question,
            "attempt_count": attempt_count,
            "previous_best_score": previous_best_score
        }
        res = predict_skill_evaluator(feature_input)
        return res.get("recommendation"), res.get("confidence")
    except Exception:
        return None, None


def combine_cv_and_assessment(
    cv_matching_result: Dict[str, Any],
    db_or_assessments: Optional[Union[Session, Dict[str, Any], List[Dict[str, Any]]]] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Combines CV matching results with assessment results without altering raw CV matching data.

    cv_matching_result: dict containing matched_skills and missing_skills
    db_or_assessments: SQLAlchemy Session OR pre-built mapping/list of assessment results
    user_id: optional user identifier
    """
    matched_input = cv_matching_result.get("matched_skills", [])
    missing_input = cv_matching_result.get("missing_skills", [])

    # Helper function to find assessment for a given skill name
    def lookup_assessment(skill_name: str) -> Optional[Dict[str, Any]]:
        if db_or_assessments is None:
            return None

        if isinstance(db_or_assessments, Session):
            return get_assessment_result_for_skill(db_or_assessments, skill_name, user_id=user_id)

        if isinstance(db_or_assessments, dict):
            # Check direct or lowercase lookup
            norm_name = skill_name.strip().lower()
            for key, val in db_or_assessments.items():
                if key.strip().lower() == norm_name:
                    if isinstance(val, dict):
                        return val
                    elif isinstance(val, str):
                        return {"assessed_level": val}
            return None

        if isinstance(db_or_assessments, list):
            norm_name = skill_name.strip().lower()
            for item in db_or_assessments:
                if isinstance(item, dict):
                    item_skill = item.get("skill", "").strip().lower()
                    if item_skill == norm_name:
                        return item
            return None

        return None

    transformed_matched = []
    for item in matched_input:
        skill_name = item.get("skill", "")
        req_level = item.get("required_level") or item.get("level", "")
        importance = item.get("importance", "")
        evidence = item.get("evidence")

        assessment_data = lookup_assessment(skill_name)
        assessed_lvl = assessment_data.get("assessed_level") if assessment_data else None

        # Level gap calculation
        level_gap = calculate_level_gap(req_level, assessed_lvl)

        # ML proficiency level prediction
        scores = extract_assessment_scores(db_or_assessments, assessment_data)
        ml_predicted_lvl = generate_ml_prediction(
            matched=True,
            required_level=req_level,
            importance=importance,
            scores=scores
        )

        model1_rec, model1_conf = generate_model1_evaluator_output(
            required_level=req_level,
            assessed_level=assessed_lvl,
            scores=scores,
            cv_level=None
        )

        total_score = scores.get("total_score") if scores else None
        
        # Calculate deterministic weakness
        weakness_info = calculate_weakness(level_gap=level_gap, total_score=total_score)
        is_weakness = weakness_info["is_weakness"]
        weakness_reason = weakness_info["weakness_reason"]
        
        # Generate rule-based recommendation
        rec_info = generate_recommendation(
            skill=skill_name,
            required_level=req_level,
            assessed_level=assessed_lvl,
            level_gap=level_gap,
            total_score=total_score,
            is_weakness=is_weakness,
            weakness_reason=weakness_reason
        )

        improvement_prob = assessment_data.get("improvement_probability") if assessment_data else None
        if improvement_prob is None and isinstance(db_or_assessments, Session) and user_id is not None:
            from app.services.longitudinal_service import predict_skill_improvement_from_history
            curr_attempt_id = assessment_data.get("attempt_id") if assessment_data else None
            improvement_prob = predict_skill_improvement_from_history(
                db=db_or_assessments,
                user_id=user_id,
                skill=skill_name,
                current_attempt_id=curr_attempt_id,
                cv_matched=True
            )

        transformed_matched.append({
            "skill": skill_name,
            "level": req_level,
            "required_level": req_level,
            "importance": importance,
            "matched": True,
            "cv_level": None,  # Strictly null per requirement
            "assessed_level": assessed_lvl,
            "ml_predicted_level": ml_predicted_lvl,
            "level_gap": level_gap,
            "total_score": total_score,
            "is_weakness": is_weakness,
            "weakness_reason": weakness_reason,
            "priority": rec_info["priority"],
            "recommendation": rec_info["recommendation"],
            "recommendation_reason": rec_info["reason"],
            "skill_recommendation": model1_rec,
            "recommendation_confidence": model1_conf,
            "evidence": evidence,
            "improvement_probability": improvement_prob
        })

    transformed_missing = []
    for item in missing_input:
        skill_name = item.get("skill", "")
        req_level = item.get("required_level") or item.get("level", "")
        importance = item.get("importance", "")

        assessment_data = lookup_assessment(skill_name)

        # ML proficiency level prediction if scores exist
        scores = extract_assessment_scores(db_or_assessments, assessment_data)
        ml_predicted_lvl = generate_ml_prediction(
            matched=False,
            required_level=req_level,
            importance=importance,
            scores=scores
        )

        total_score = scores.get("total_score") if scores else None
        
        # Assessed level and gap for missing skills (usually None initially unless previously assessed)
        assessed_lvl = assessment_data.get("assessed_level") if assessment_data else None
        level_gap = calculate_level_gap(req_level, assessed_lvl)

        model1_rec, model1_conf = generate_model1_evaluator_output(
            required_level=req_level,
            assessed_level=assessed_lvl,
            scores=scores,
            cv_level=None
        )
        
        # Calculate deterministic weakness
        weakness_info = calculate_weakness(level_gap=level_gap, total_score=total_score)
        is_weakness = weakness_info["is_weakness"]
        weakness_reason = weakness_info["weakness_reason"]
        
        # Generate rule-based recommendation
        rec_info = generate_recommendation(
            skill=skill_name,
            required_level=req_level,
            assessed_level=assessed_lvl,
            level_gap=level_gap,
            total_score=total_score,
            is_weakness=is_weakness,
            weakness_reason=weakness_reason
        )

        missing_improvement_prob = assessment_data.get("improvement_probability") if assessment_data else None
        if missing_improvement_prob is None and isinstance(db_or_assessments, Session) and user_id is not None:
            from app.services.longitudinal_service import predict_skill_improvement_from_history
            curr_attempt_id = assessment_data.get("attempt_id") if assessment_data else None
            missing_improvement_prob = predict_skill_improvement_from_history(
                db=db_or_assessments,
                user_id=user_id,
                skill=skill_name,
                current_attempt_id=curr_attempt_id,
                cv_matched=False
            )

        transformed_missing.append({
            "skill": skill_name,
            "level": req_level,
            "required_level": req_level,
            "importance": importance,
            "matched": False,
            "cv_level": None,  # Strictly null per requirement
            "assessed_level": assessed_lvl,
            "ml_predicted_level": ml_predicted_lvl,
            "level_gap": level_gap,
            "total_score": total_score,
            "is_weakness": is_weakness,
            "weakness_reason": weakness_reason,
            "priority": rec_info["priority"],
            "recommendation": rec_info["recommendation"],
            "recommendation_reason": rec_info["reason"],
            "skill_recommendation": model1_rec,
            "recommendation_confidence": model1_conf,
            "evidence": None,
            "improvement_probability": missing_improvement_prob
        })

    transformed_skills = transformed_matched + transformed_missing

    combined_result = {
        "filename": cv_matching_result.get("filename"),
        "pages": cv_matching_result.get("pages"),
        "matched_skills": transformed_matched,
        "missing_skills": transformed_missing,
        "skills": transformed_skills,
        "score_data": cv_matching_result.get("score_data")
    }

    try:
        from app.ml.predict_readiness import predict_final_recommendation
        model2_output = predict_final_recommendation(combined_result)
        combined_result["final_verdict"] = model2_output.get("final_verdict")
        combined_result["recommendation_confidence"] = model2_output.get("confidence")
        combined_result["priority_skills"] = model2_output.get("priority_skills")
    except Exception:
        combined_result["final_verdict"] = None
        combined_result["recommendation_confidence"] = None
        combined_result["priority_skills"] = None

    return combined_result


