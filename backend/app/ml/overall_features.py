"""
OVERALL JOB READINESS FEATURE ENGINEERING

Converts combined per-skill analysis result dictionary into a fixed-length
feature dictionary suitable for an overall job readiness ML model.
"""

from typing import Dict, Any, List
import numpy as np

LEVEL_MAP: Dict[str, int] = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3
}

DEFAULT_FEATURE_KEYS: List[str] = [
    "total_skill_count",
    "required_skill_count",
    "preferred_skill_count",
    "cv_match_ratio",
    "required_skills_match_ratio",
    "preferred_skills_match_ratio",
    "assessed_skills_ratio",
    "required_assessment_coverage",
    "avg_assessment_score",
    "avg_level_gap",
    "max_level_gap",
    "zero_gap_skills_ratio",
    "ml_meets_req_ratio",
    "cv_matching_score",
]


def build_overall_features(combined_analysis: Dict[str, Any]) -> Dict[str, float]:
    """
    Extracts a fixed-length dictionary of 14 numeric features from a combined
    per-skill analysis result dictionary (output of combine_cv_and_assessment).

    Parameters:
        combined_analysis (dict): Dictionary containing skill breakdown and CV matching data.

    Returns:
        dict: Feature dictionary containing all 14 required feature keys.
    """
    if not isinstance(combined_analysis, dict):
        raise ValueError(f"Input must be a dictionary, got {type(combined_analysis).__name__}")

    # Extract skills list from 'skills' or fall back to 'matched_skills' + 'missing_skills'
    skills = combined_analysis.get("skills")
    if skills is None:
        matched_input = combined_analysis.get("matched_skills", [])
        missing_input = combined_analysis.get("missing_skills", [])
        if isinstance(matched_input, list) or isinstance(missing_input, list):
            skills = (matched_input if isinstance(matched_input, list) else []) + \
                     (missing_input if isinstance(missing_input, list) else [])
        else:
            skills = []
    elif not isinstance(skills, list):
        skills = []

    # 1, 2 & 3. Skill Counts
    total_skill_count = len(skills)

    req_skills = [s for s in skills if str(s.get("importance", "")).lower().strip() == "required"]
    pref_skills = [s for s in skills if str(s.get("importance", "")).lower().strip() == "preferred"]

    required_skill_count = len(req_skills)
    preferred_skill_count = len(pref_skills)

    # 4. CV Match Ratio
    cv_matched_count = sum(1 for s in skills if bool(s.get("matched")))
    cv_match_ratio = round(cv_matched_count / total_skill_count, 4) if total_skill_count > 0 else 0.0

    # 5. Required Skills Match Ratio
    if required_skill_count > 0:
        req_matched_count = sum(1 for s in req_skills if bool(s.get("matched")))
        required_skills_match_ratio = round(req_matched_count / required_skill_count, 4)
    else:
        required_skills_match_ratio = 0.0

    # 6. Preferred Skills Match Ratio
    if preferred_skill_count > 0:
        pref_matched_count = sum(1 for s in pref_skills if bool(s.get("matched")))
        preferred_skills_match_ratio = round(pref_matched_count / preferred_skill_count, 4)
    else:
        preferred_skills_match_ratio = 0.0

    # 7. Assessed Skills Ratio
    assessed_items = [
        s for s in skills
        if s.get("assessed_level") is not None or s.get("level_gap") is not None or s.get("total_score") is not None
    ]
    assessed_skills_count = len(assessed_items)
    assessed_skills_ratio = round(assessed_skills_count / total_skill_count, 4) if total_skill_count > 0 else 0.0

    # 8. Required Assessment Coverage
    if required_skill_count > 0:
        assessed_req_count = sum(
            1 for s in req_skills
            if s.get("assessed_level") is not None or s.get("level_gap") is not None or s.get("total_score") is not None
        )
        required_assessment_coverage = round(assessed_req_count / required_skill_count, 4)
    else:
        required_assessment_coverage = 0.0

    # 9. Average Assessment Score
    scores_list = []
    for s in assessed_items:
        if "total_score" in s and s["total_score"] is not None:
            try:
                scores_list.append(float(s["total_score"]))
            except (ValueError, TypeError):
                pass
        elif "score" in s and s["score"] is not None:
            try:
                scores_list.append(float(s["score"]))
            except (ValueError, TypeError):
                pass
        elif "scores" in s and isinstance(s["scores"], dict) and "total_score" in s["scores"]:
            try:
                scores_list.append(float(s["scores"]["total_score"]))
            except (ValueError, TypeError):
                pass

    if scores_list:
        avg_assessment_score = round(float(np.mean(scores_list)), 4)
    else:
        avg_assessment_score = 0.0

    # 10, 11 & 12. Level Gap Metrics (Avg, Max, Zero Gap Ratio)
    gaps = [int(s["level_gap"]) for s in skills if s.get("level_gap") is not None]

    if gaps:
        avg_level_gap = round(float(np.mean(gaps)), 4)
        max_level_gap = float(np.max(gaps))
        zero_gap_count = sum(1 for g in gaps if g == 0)
        zero_gap_skills_ratio = round(zero_gap_count / len(gaps), 4)
    else:
        avg_level_gap = 0.0
        max_level_gap = 0.0
        zero_gap_skills_ratio = 0.0

    # 13. ML Predicted Level vs Required Level Comparison Ratio
    ml_eval_count = 0
    ml_meets_req_count = 0

    for s in skills:
        pred_lvl_str = s.get("ml_predicted_level")
        if pred_lvl_str:
            req_lvl_str = str(s.get("required_level") or s.get("level", "")).lower().strip()
            pred_lvl_clean = str(pred_lvl_str).lower().strip()

            if req_lvl_str in LEVEL_MAP and pred_lvl_clean in LEVEL_MAP:
                ml_eval_count += 1
                if LEVEL_MAP[pred_lvl_clean] >= LEVEL_MAP[req_lvl_str]:
                    ml_meets_req_count += 1

    if ml_eval_count > 0:
        ml_meets_req_ratio = round(ml_meets_req_count / ml_eval_count, 4)
    else:
        ml_meets_req_ratio = 0.0

    # 14. CV Matching Score
    score_data = combined_analysis.get("score_data")
    cv_matching_score = 0.0

    if isinstance(score_data, dict):
        raw_score = score_data.get("score")
        if raw_score is not None:
            try:
                score_val = float(raw_score)
                if score_val > 1.0:
                    cv_matching_score = round(score_val / 100.0, 4)
                else:
                    cv_matching_score = round(score_val, 4)
            except (ValueError, TypeError):
                cv_matching_score = 0.0

    return {
        "total_skill_count": float(total_skill_count),
        "required_skill_count": float(required_skill_count),
        "preferred_skill_count": float(preferred_skill_count),
        "cv_match_ratio": float(cv_match_ratio),
        "required_skills_match_ratio": float(required_skills_match_ratio),
        "preferred_skills_match_ratio": float(preferred_skills_match_ratio),
        "assessed_skills_ratio": float(assessed_skills_ratio),
        "required_assessment_coverage": float(required_assessment_coverage),
        "avg_assessment_score": float(avg_assessment_score),
        "avg_level_gap": float(avg_level_gap),
        "max_level_gap": float(max_level_gap),
        "zero_gap_skills_ratio": float(zero_gap_skills_ratio),
        "ml_meets_req_ratio": float(ml_meets_req_ratio),
        "cv_matching_score": float(cv_matching_score),
    }


def extract_overall_features(combined_analysis: Dict[str, Any]) -> Dict[str, float]:
    """Alias for build_overall_features."""
    return build_overall_features(combined_analysis)
