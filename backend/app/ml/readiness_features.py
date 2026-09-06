"""
MODEL 2: FINAL JOB RECOMMENDATION FEATURE ENGINEERING & PRIORITY RANKING

Converts candidate job analysis results into a 10-feature vector for Model 2 prediction,
and calculates transparent skill priority rankings.
"""

from typing import Dict, Any, List, Optional
import numpy as np

LEVEL_MAP: Dict[str, int] = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3
}

MODEL2_FEATURES: List[str] = [
    "total_required_skills",
    "missing_skills_count",
    "average_skill_gap",
    "overall_assessment_accuracy",
    "upgrade_needed_count",
    "mastered_count",
    "speed_practice_count",
    "relearn_basics_count",
    "assessed_skills_count",
    "assessment_completion_rate"
]


def extract_model2_features(combined_analysis: Dict[str, Any]) -> Dict[str, float]:
    """
    Extracts the 10 aggregated candidate-job feature signals for Model 2.

    Parameters:
        combined_analysis (dict): Dictionary containing skill breakdown and CV/assessment results.

    Returns:
        dict: Feature dictionary containing all 10 required Model 2 feature keys.
    """
    if not isinstance(combined_analysis, dict):
        raise ValueError(f"Input must be a dictionary, got {type(combined_analysis).__name__}")

    # Extract skills list from 'skills' or combine 'matched_skills' + 'missing_skills'
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

    total_required_skills = len(skills)

    # Missing skills count
    missing_input = combined_analysis.get("missing_skills")
    if isinstance(missing_input, list):
        missing_skills_count = len(missing_input)
    else:
        missing_skills_count = sum(1 for s in skills if not bool(s.get("matched", True)))

    # Skill gaps and assessment accuracy
    gaps: List[float] = []
    assessment_scores: List[float] = []
    assessed_count = 0

    upgrade_needed_count = 0
    mastered_count = 0
    speed_practice_count = 0
    relearn_basics_count = 0

    for s in skills:
        matched = bool(s.get("matched", True))
        lvl_gap = s.get("level_gap")
        total_score = s.get("total_score")
        assessed_lvl = s.get("assessed_level")
        rec = s.get("skill_recommendation")

        # Track Model 1 recommendations
        if rec == "Upgrade Needed":
            upgrade_needed_count += 1
        elif rec == "Mastered":
            mastered_count += 1
        elif rec == "Speed Practice":
            speed_practice_count += 1
        elif rec == "Re-learn Basics":
            relearn_basics_count += 1

        # Track assessed skills & scores
        if assessed_lvl is not None or total_score is not None or lvl_gap is not None:
            assessed_count += 1

        if total_score is not None:
            try:
                assessment_scores.append(float(total_score))
            except (ValueError, TypeError):
                pass

        # Calculate skill level gap safely
        if lvl_gap is not None:
            try:
                gaps.append(max(0.0, float(lvl_gap)))
            except (ValueError, TypeError):
                gaps.append(0.0)
        elif not matched:
            # Unassessed missing skill: compute level gap from required_level vs candidate(0)
            req_str = str(s.get("required_level") or s.get("level", "basic")).lower().strip()
            gaps.append(float(LEVEL_MAP.get(req_str, 1)))
        else:
            # Unassessed matched skill
            gaps.append(0.0)

    average_skill_gap = round(float(np.mean(gaps)), 4) if gaps else 0.0
    overall_assessment_accuracy = round(float(np.mean(assessment_scores)), 4) if assessment_scores else 0.0

    assessed_skills_count = assessed_count
    assessment_completion_rate = (
        round(float(assessed_skills_count) / float(total_required_skills), 4)
        if total_required_skills > 0 else 0.0
    )

    return {
        "total_required_skills": float(total_required_skills),
        "missing_skills_count": float(missing_skills_count),
        "average_skill_gap": average_skill_gap,
        "overall_assessment_accuracy": overall_assessment_accuracy,
        "upgrade_needed_count": float(upgrade_needed_count),
        "mastered_count": float(mastered_count),
        "speed_practice_count": float(speed_practice_count),
        "relearn_basics_count": float(relearn_basics_count),
        "assessed_skills_count": float(assessed_skills_count),
        "assessment_completion_rate": assessment_completion_rate
    }


def calculate_skill_priority_score(skill_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates transparent priority score and explanation for a single skill.

    Formula:
        priority_score = normalized_skill_gap * requirement_importance * weakness_factor
    """
    req_level_str = str(skill_item.get("required_level") or skill_item.get("level", "basic")).lower().strip()
    req_level_val = LEVEL_MAP.get(req_level_str, 1)

    level_gap = skill_item.get("level_gap")
    matched = bool(skill_item.get("matched", True))

    if level_gap is not None:
        normalized_skill_gap = min(1.0, max(0.0, float(level_gap) / 3.0))
    elif not matched:
        normalized_skill_gap = min(1.0, max(0.33, float(req_level_val) / 3.0))
    else:
        normalized_skill_gap = 0.1

    importance_str = str(skill_item.get("importance", "")).lower().strip()
    if importance_str == "required":
        requirement_importance = 1.0
    elif importance_str == "preferred":
        requirement_importance = 0.7
    else:
        requirement_importance = 0.85

    rec = skill_item.get("skill_recommendation")
    if rec == "Re-learn Basics":
        weakness_factor = 1.3
        reason = "Skill requires fundamental re-learning"
    elif rec == "Upgrade Needed":
        weakness_factor = 1.2
        reason = "Skill level gap identified, upgrade needed"
    elif rec == "Speed Practice":
        weakness_factor = 1.0
        reason = "Skill level met but speed practice recommended"
    elif rec == "Mastered":
        weakness_factor = 0.2
        reason = "Skill fully mastered"
    elif not matched:
        weakness_factor = 1.1
        reason = "Required skill missing from CV"
    elif level_gap is not None and level_gap > 0:
        weakness_factor = 1.1
        reason = f"Level gap of {level_gap} identified"
    else:
        weakness_factor = 0.4
        reason = "Requirement met or pending assessment"

    if normalized_skill_gap >= 0.6 and requirement_importance >= 0.9:
        reason = "Large skill gap and high job requirement"

    raw_score = normalized_skill_gap * requirement_importance * weakness_factor
    priority_score = round(float(np.clip(raw_score, 0.0, 1.0)), 4)

    return {
        "skill": skill_item.get("skill", ""),
        "priority_score": priority_score,
        "reason": reason,
        "required_level": skill_item.get("required_level") or skill_item.get("level"),
        "assessed_level": skill_item.get("assessed_level"),
        "level_gap": level_gap,
        "skill_recommendation": skill_item.get("skill_recommendation"),
        "recommendation_confidence": skill_item.get("recommendation_confidence")
    }


def compute_priority_skills(skills: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Computes priority scores for all required skills and returns the top N ranked skills.
    """
    if not skills:
        return []

    ranked = [calculate_skill_priority_score(s) for s in skills]

    # Sort deterministically by priority_score desc, then skill name asc
    ranked.sort(key=lambda x: (-x["priority_score"], str(x["skill"]).lower()))
    return ranked[:top_n]
