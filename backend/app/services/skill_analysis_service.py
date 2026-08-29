from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import AssessmentAttempt, AssessmentAnswer, AssessmentQuestion
from app.services.matching_service import get_skill_variants
from app.ml.predict import SkillLevelPredictor

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

    query = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.completed_at.isnot(None),
            AssessmentAttempt.assessed_level.isnot(None)
        )
    )

    if user_id is not None:
        query = query.filter(AssessmentAttempt.user_id == user_id)

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

    return {
        "attempt_id": matched_attempt.id,
        "skill": matched_attempt.skill,
        "required_level": matched_attempt.required_level,
        "assessed_level": matched_attempt.assessed_level,
        "level_gap": gap
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
            "evidence": evidence
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

        transformed_missing.append({
            "skill": skill_name,
            "level": req_level,
            "required_level": req_level,
            "importance": importance,
            "matched": False,
            "cv_level": None,  # Strictly null per requirement
            "assessed_level": None,
            "ml_predicted_level": ml_predicted_lvl,
            "level_gap": None,
            "evidence": None
        })

    transformed_skills = transformed_matched + transformed_missing

    return {
        "filename": cv_matching_result.get("filename"),
        "pages": cv_matching_result.get("pages"),
        "matched_skills": transformed_matched,
        "missing_skills": transformed_missing,
        "skills": transformed_skills,
        "score_data": cv_matching_result.get("score_data")
    }


