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
    user_id: Optional[int] = None,
    analysis_id: Optional[int] = None,
    include_prior: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Retrieves completed assessment result for a given skill.
    If include_prior is False, strictly checks attempts for the given analysis_id.
    """
    if not skill or not skill.strip():
        return None

    skill_clean = skill.strip()
    variants = get_skill_variants(skill_clean)
    variants_lower = [v.lower() for v in variants]

    if user_id is None:
        return None

    base_query = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.completed_at.isnot(None),
        AssessmentAttempt.user_id == user_id,
    ).order_by(AssessmentAttempt.completed_at.desc(), AssessmentAttempt.id.desc())

    if analysis_id is not None:
        session_attempts = base_query.filter(AssessmentAttempt.analysis_id == analysis_id).all()
        if session_attempts or not include_prior:
            attempts = session_attempts
        else:
            attempts = base_query.all()
    else:
        attempts = base_query.all() if include_prior else []

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

    # Calculate retake telemetry (attempt_count and previous_best_score)
    all_skill_attempts = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.user_id == user_id,
        AssessmentAttempt.completed_at.isnot(None),
        func.lower(AssessmentAttempt.skill).in_(variants_lower + [skill_clean.lower()])
    ).order_by(AssessmentAttempt.completed_at.asc(), AssessmentAttempt.id.asc()).all()

    attempt_count = max(1, len(all_skill_attempts))
    prior_scores = []
    for att in all_skill_attempts:
        if att.id != matched_attempt.id:
            att_scores = extract_assessment_scores(db, {"attempt_id": att.id})
            if att_scores and att_scores.get("total_score") is not None:
                prior_scores.append(float(att_scores["total_score"]))
    
    previous_best_score = max(prior_scores) if prior_scores else (scores.get("total_score") if scores else None)

    model1_rec, model1_conf = generate_model1_evaluator_output(
        required_level=matched_attempt.required_level,
        assessed_level=assessed_lvl,
        scores=scores,
        cv_level=matched_attempt.cv_level,
        attempt_count=attempt_count,
        previous_best_score=previous_best_score
    )

    return {
        "attempt_id": matched_attempt.id,
        "skill": matched_attempt.skill,
        "required_level": matched_attempt.required_level,
        "assessed_level": assessed_lvl,
        "level_gap": gap,
        "total_score": scores.get("total_score") if scores else None,
        "skill_recommendation": model1_rec,
        "recommendation_confidence": model1_conf,
        "improvement_probability": improvement_prob,
        "attempt_count": attempt_count,
        "previous_best_score": previous_best_score
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

    if assessment_data.get("total_score") is not None:
        b_s = float(assessment_data.get("basic_score") or 0.0)
        i_s = float(assessment_data.get("intermediate_score") or 0.0)
        a_s = float(assessment_data.get("advanced_score") or 0.0)
        t_s = float(assessment_data["total_score"])
        return {
            "basic_score": b_s,
            "intermediate_score": i_s,
            "advanced_score": a_s,
            "total_score": t_s
        }

    # Check if sub-scores are directly provided in assessment_data dictionary
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
            q_obj = getattr(ans, "question_obj", None)
            q_lvl = getattr(q_obj, "level", None) if q_obj else None
            lvl = str(q_lvl).lower() if q_lvl else None
            if lvl in level_counts:
                level_counts[lvl]["total"] += 1
                if bool(getattr(ans, "is_correct", False)):
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
    user_id: Optional[int] = None,
    analysis_id: Optional[int] = None,
    include_prior: bool = True,
) -> Dict[str, Any]:
    """
    Combines CV matching results with assessment results without altering raw CV matching data.

    cv_matching_result: dict containing matched_skills and missing_skills
    db_or_assessments: SQLAlchemy Session OR pre-built mapping/list of assessment results
    user_id: optional user identifier
    include_prior: whether to fall back to older assessments from previous sessions
    """
    matched_input = cv_matching_result.get("matched_skills", [])
    missing_input = cv_matching_result.get("missing_skills", [])

    matched_skill_names = {s.get("skill", "").strip().lower() for s in matched_input if isinstance(s, dict) and s.get("skill")}

    raw_skills = cv_matching_result.get("skills")
    if not raw_skills:
        raw_skills = matched_input + missing_input

    transformed_matched = []
    transformed_missing = []

    # Helper function to find assessment for a given skill name
    def lookup_assessment(skill_name: str) -> Optional[Dict[str, Any]]:
        if db_or_assessments is None:
            return None

        if isinstance(db_or_assessments, Session):
            return get_assessment_result_for_skill(
                db_or_assessments,
                skill_name,
                user_id=user_id,
                analysis_id=analysis_id,
                include_prior=include_prior,
            )

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

    for item in raw_skills:
        skill_name = item.get("skill", "")
        norm_name = skill_name.strip().lower()
        req_level = item.get("required_level") or item.get("level", "")
        importance = item.get("importance", "required")
        evidence = item.get("evidence")

        # CV Evaluation fields (strictly independent from assessment quiz results)
        cv_match_status = item.get("cv_match_status")
        if not cv_match_status:
            if item.get("matched") is True or norm_name in matched_skill_names:
                cv_match_status = "Match"
            else:
                cv_match_status = "Missing"

        cv_level = item.get("cv_level")
        if cv_level is None and cv_match_status in ["Match", "Needs Improvement"]:
            cv_level = "unspecified"

        matched_flag = (cv_match_status in ["Match", "Needs Improvement"])

        # Assessment lookups (isolated from cv_match_status and cv_level)
        assessment_data = lookup_assessment(skill_name)
        assessed_lvl = assessment_data.get("assessed_level") if assessment_data else None

        # Level gap calculation:
        # If assessed: calculate gap between required level and assessed level
        # If unassessed: calculate gap based on CV evidence (or missing status)
        req_clean = (req_level or "basic").strip().lower()
        req_val = LEVEL_MAP.get(req_clean, 1)

        scores = extract_assessment_scores(db_or_assessments, assessment_data)
        total_score = scores.get("total_score") if scores else None

        if assessed_lvl is not None:
            # Assessed skill evaluation
            level_gap = calculate_level_gap(req_level, assessed_lvl)
            weakness_info = calculate_weakness(level_gap=level_gap, total_score=total_score)
            is_weakness = weakness_info["is_weakness"]
            weakness_reason = weakness_info["weakness_reason"]

            model1_rec = assessment_data.get("skill_recommendation") if assessment_data else None
            model1_conf = assessment_data.get("recommendation_confidence") if assessment_data else None
            if not model1_rec:
                model1_rec, model1_conf = generate_model1_evaluator_output(
                    required_level=req_level,
                    assessed_level=assessed_lvl,
                    scores=scores,
                    cv_level=cv_level,
                    attempt_count=assessment_data.get("attempt_count", 1) if assessment_data else 1,
                    previous_best_score=assessment_data.get("previous_best_score") if assessment_data else None
                )
        else:
            # Unassessed skill: level_gap is strictly None until assessed
            level_gap = None
            if not matched_flag or cv_match_status == "Missing":
                is_weakness = True
                weakness_reason = "UNVERIFIED_IN_CV"
            elif cv_match_status == "Needs Improvement":
                is_weakness = True
                weakness_reason = "LEVEL_GAP"
            else:
                is_weakness = False
                weakness_reason = "NONE"
            model1_rec = None
            model1_conf = None

        # ML proficiency level prediction (for score interpolation)
        ml_predicted_lvl = generate_ml_prediction(
            matched=matched_flag,
            required_level=req_level,
            importance=importance,
            scores=scores
        )

        # Generate contextual recommendation and priority
        is_pref = (importance or "required").strip().lower() == "preferred"
        if is_weakness:
            if is_pref:
                priority = "MEDIUM" if (level_gap and level_gap >= 2) else "LOW"
            else:
                # Confirmed assessed failure or severe gap is HIGH priority; unverified CV missing is MEDIUM priority
                if (level_gap and level_gap >= 2) or weakness_reason in ["LEVEL_GAP_AND_LOW_SCORE"] or (total_score is not None and total_score < 0.40):
                    priority = "HIGH"
                elif weakness_reason in ["UNVERIFIED_IN_CV", "MISSING_SKILL"]:
                    priority = "MEDIUM"
                else:
                    priority = "MEDIUM"
        else:
            priority = "LOW"

        if assessed_lvl is not None:
            if is_weakness:
                score_str = f"{int(total_score * 100)}%" if total_score is not None else "0%"
                recommendation = f"Targeted practice required to elevate {skill_name} from {assessed_lvl} to {req_level}."
                rec_reason = f"Assessment score: {score_str} ({assessed_lvl} level vs {req_level} required)."
            else:
                score_str = f"{int(total_score * 100)}%" if total_score is not None else "100%"
                recommendation = f"Proficiency verified at {assessed_lvl} level. Maintain skills with ongoing practice."
                rec_reason = f"Candidate demonstrated {assessed_lvl} proficiency matching job requirement ({score_str} score)."
        else:
            if weakness_reason in ["UNVERIFIED_IN_CV", "MISSING_SKILL"]:
                recommendation = f"Skill not mentioned in CV (unverified). Take assessment to demonstrate proficiency or update your CV."
                rec_reason = "Skill was not identified in CV evidence. Candidate may possess this skill; assessment recommended to verify."
            elif weakness_reason == "LEVEL_GAP":
                recommendation = f"CV indicates {cv_level} level, but job requires {req_level}. Take assessment to verify true proficiency."
                rec_reason = f"Identified CV level ({cv_level}) is below target requirement ({req_level})."
            else:
                recommendation = f"Candidate satisfies {req_level} requirement based on CV evidence. Assessment optional for verification."
                rec_reason = f"CV contains evidence satisfying {req_level} level standard."

        improvement_prob = assessment_data.get("improvement_probability") if assessment_data else None
        if improvement_prob is None and isinstance(db_or_assessments, Session) and user_id is not None:
            from app.services.longitudinal_service import predict_skill_improvement_from_history
            curr_attempt_id = assessment_data.get("attempt_id") if assessment_data else None
            improvement_prob = predict_skill_improvement_from_history(
                db=db_or_assessments,
                user_id=user_id,
                skill=skill_name,
                current_attempt_id=curr_attempt_id,
                cv_matched=matched_flag
            )

        entry = {
            "skill": skill_name,
            "level": req_level,
            "required_level": req_level,
            "importance": importance,
            "matched": matched_flag,
            "cv_level": cv_level,
            "cv_match_status": cv_match_status,
            "assessed_level": assessed_lvl,
            "ml_predicted_level": ml_predicted_lvl,
            "level_gap": level_gap,
            "total_score": total_score,
            "is_weakness": is_weakness,
            "weakness_reason": weakness_reason,
            "priority": priority,
            "recommendation": recommendation,
            "recommendation_reason": rec_reason,
            "skill_recommendation": model1_rec,
            "recommendation_confidence": model1_conf,
            "evidence": evidence,
            "improvement_probability": improvement_prob,
            "actionable_feedback": item.get("actionable_feedback")
        }

        if cv_match_status in ["Match", "Needs Improvement"]:
            transformed_matched.append(entry)
        else:
            transformed_missing.append(entry)

    transformed_skills = transformed_matched + transformed_missing

    # Re-calculate simple CV match score data
    total_skills = len(transformed_skills)
    matched_count = len(transformed_matched)
    missing_count = len(transformed_missing)
    cv_score = round((matched_count / total_skills) * 100, 2) if total_skills > 0 else 0.0

    score_data = {
        "total_skills": total_skills,
        "matched_count": matched_count,
        "missing_count": missing_count,
        "score": cv_score
    }

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
        combined_result["readiness_verdict"] = model2_output.get("readiness_verdict") or model2_output.get("final_verdict")
        combined_result["readiness_reasons"] = model2_output.get("readiness_reasons")
        combined_result["recommendation_confidence"] = model2_output.get("confidence")
        combined_result["priority_skills"] = model2_output.get("priority_skills")
        combined_result["is_preliminary"] = model2_output.get("is_preliminary", True)
        combined_result["verification_status"] = model2_output.get("verification_status", "Unverified (Preliminary CV Evidence)")
    except Exception:
        combined_result["final_verdict"] = None
        combined_result["readiness_verdict"] = None
        combined_result["readiness_reasons"] = None
        combined_result["recommendation_confidence"] = None
        combined_result["priority_skills"] = None
        combined_result["is_preliminary"] = True
        combined_result["verification_status"] = "Unverified (Preliminary CV Evidence)"

    return combined_result
