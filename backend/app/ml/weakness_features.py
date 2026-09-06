"""
WEAKNESS ML FEATURE EXTRACTION MODULE

Extracts ML-ready per-skill feature vectors and cross-skill candidate context
from completed assessment attempt data at completion time (t1).

Strictly input feature extraction only. Does NOT produce priority labels,
improvement probabilities, or weighted readiness scores.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Union, Optional, Tuple
import numpy as np

LEVEL_NUMERIC_MAP: Dict[str, int] = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3
}

FEATURE_KEYS: List[str] = [
    "skill",
    "required_level",
    "assessed_level",
    "level_gap",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "total_score",
    "questions_answered_count",
    "avg_answer_time_seconds",
    "answer_time_std_seconds",
    "min_answer_time_seconds",
    "max_answer_time_seconds",
    "timed_questions_count",
    "candidate_avg_total_score",
    "candidate_score_std",
    "candidate_below_requirement_ratio",
    "candidate_avg_answer_time_seconds",
]


def parse_level(val: Any, default: int = 0) -> int:
    """
    Converts a level representation (string or int) into its numeric value:
    basic=1, intermediate=2, advanced=3. Returns default if unassessed or invalid.
    """
    if isinstance(val, int):
        return val if val in (1, 2, 3) else default
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if cleaned in LEVEL_NUMERIC_MAP:
            return LEVEL_NUMERIC_MAP[cleaned]
    return default


def parse_datetime(dt_val: Any) -> Optional[datetime]:
    """
    Safely parses datetime objects, ISO strings, or numeric timestamps.
    """
    if dt_val is None:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, (int, float)):
        try:
            return datetime.fromtimestamp(dt_val, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(dt_val, str):
        cleaned = dt_val.strip()
        if not cleaned:
            return None
        # Replace trailing 'Z' if present for isoformat parsing
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def extract_answer_info(ans: Any) -> Tuple[Optional[str], bool, Optional[datetime]]:
    """
    Extracts (level, is_correct, answered_at) from an answer dict or ORM object.
    """
    is_correct = False
    level = None
    answered_at = None

    if isinstance(ans, dict):
        is_correct = bool(ans.get("is_correct", False))

        # Check level locations in dict
        level = (
            ans.get("level")
            or ans.get("question_level")
            or (ans.get("question") if isinstance(ans.get("question"), dict) else {}).get("level")
            or (ans.get("question_obj") if isinstance(ans.get("question_obj"), dict) else {}).get("level")
        )

        dt_raw = ans.get("answered_at")
        answered_at = parse_datetime(dt_raw)
    else:
        # ORM object handling
        is_correct = bool(getattr(ans, "is_correct", False))

        level = getattr(ans, "level", None)
        if level is None:
            q_obj = getattr(ans, "question_obj", None) or getattr(ans, "question", None)
            if q_obj is not None:
                level = getattr(q_obj, "level", None)

        dt_raw = getattr(ans, "answered_at", None)
        answered_at = parse_datetime(dt_raw)

    level_str = str(level).strip().lower() if level else None
    return level_str, is_correct, answered_at


def compute_timing_metrics(answers: List[Any]) -> Tuple[Dict[str, Any], List[float]]:
    """
    Computes timing features from consecutive answer timestamps.
    Returns (timing_dict, valid_intervals_list).
    """
    # Extract timestamps along with answer order
    timestamps: List[datetime] = []
    for ans in answers:
        _, _, dt = extract_answer_info(ans)
        if dt is not None:
            timestamps.append(dt)

    intervals: List[float] = []
    if len(timestamps) >= 2:
        for i in range(len(timestamps) - 1):
            dt_diff = (timestamps[i + 1] - timestamps[i]).total_seconds()
            # Handle negative timestamp differences safely (drop invalid)
            if dt_diff >= 0.0:
                intervals.append(dt_diff)

    if not intervals:
        return {
            "avg_answer_time_seconds": 0.0,
            "answer_time_std_seconds": 0.0,
            "min_answer_time_seconds": 0.0,
            "max_answer_time_seconds": 0.0,
            "timed_questions_count": 0,
        }, []

    avg_time = round(float(np.mean(intervals)), 4)
    std_time = round(float(np.std(intervals)), 4)
    min_time = round(float(np.min(intervals)), 4)
    max_time = round(float(np.max(intervals)), 4)
    timed_count = len(intervals)

    return {
        "avg_answer_time_seconds": avg_time,
        "answer_time_std_seconds": std_time,
        "min_answer_time_seconds": min_time,
        "max_answer_time_seconds": max_time,
        "timed_questions_count": timed_count,
    }, intervals


def extract_skill_scores(attempt_or_dict: Any) -> Dict[str, Any]:
    """
    Extracts or computes per-skill score features and question counts.
    """
    # 1. Check if total_score is pre-computed on dict/object
    if isinstance(attempt_or_dict, dict) and "total_score" in attempt_or_dict:
        answers_list = attempt_or_dict.get("answers") or attempt_or_dict.get("submitted_answers") or []
        q_count = attempt_or_dict.get("questions_answered_count", len(answers_list))
        return {
            "basic_score": round(float(attempt_or_dict.get("basic_score", 0.0)), 4),
            "intermediate_score": round(float(attempt_or_dict.get("intermediate_score", 0.0)), 4),
            "advanced_score": round(float(attempt_or_dict.get("advanced_score", 0.0)), 4),
            "total_score": round(float(attempt_or_dict["total_score"]), 4),
            "questions_answered_count": int(q_count),
        }
    elif not isinstance(attempt_or_dict, dict) and hasattr(attempt_or_dict, "total_score") and getattr(attempt_or_dict, "total_score") is not None:
        answers_list = getattr(attempt_or_dict, "answers", None) or getattr(attempt_or_dict, "submitted_answers", None) or []
        q_count = getattr(attempt_or_dict, "questions_answered_count", len(answers_list))
        return {
            "basic_score": round(float(getattr(attempt_or_dict, "basic_score", 0.0)), 4),
            "intermediate_score": round(float(getattr(attempt_or_dict, "intermediate_score", 0.0)), 4),
            "advanced_score": round(float(getattr(attempt_or_dict, "advanced_score", 0.0)), 4),
            "total_score": round(float(getattr(attempt_or_dict, "total_score")), 4),
            "questions_answered_count": int(q_count),
        }

    # 2. Extract answers list and compute from scratch
    if isinstance(attempt_or_dict, dict):
        answers = attempt_or_dict.get("answers") or attempt_or_dict.get("submitted_answers") or []
    else:
        answers = getattr(attempt_or_dict, "answers", None) or getattr(attempt_or_dict, "submitted_answers", None) or []

    level_counts = {"basic": {"correct": 0, "total": 0},
                    "intermediate": {"correct": 0, "total": 0},
                    "advanced": {"correct": 0, "total": 0}}

    total_correct = 0
    total_answered = 0

    for ans in answers:
        lvl_str, is_correct, _ = extract_answer_info(ans)
        total_answered += 1
        if is_correct:
            total_correct += 1

        if lvl_str in level_counts:
            level_counts[lvl_str]["total"] += 1
            if is_correct:
                level_counts[lvl_str]["correct"] += 1

    def calc_level_score(lvl: str) -> float:
        stats = level_counts[lvl]
        t = stats["total"]
        c = stats["correct"]
        if t == 0:
            return 0.0
        denom = max(5, t)
        return round(float(c / denom), 4)

    basic_score = calc_level_score("basic")
    inter_score = calc_level_score("intermediate")
    adv_score = calc_level_score("advanced")

    total_score = round(float(total_correct / total_answered), 4) if total_answered > 0 else 0.0

    return {
        "basic_score": basic_score,
        "intermediate_score": inter_score,
        "advanced_score": adv_score,
        "total_score": total_score,
        "questions_answered_count": total_answered,
    }


def extract_single_skill_features(attempt_or_dict: Any) -> Tuple[Dict[str, Any], List[float]]:
    """
    Extracts single skill features and returns (partially_filled_feature_dict, timing_intervals).
    """
    if isinstance(attempt_or_dict, dict):
        skill_name = str(attempt_or_dict.get("skill", "")).strip()
        req_lvl_raw = attempt_or_dict.get("required_level", "basic")
        assessed_lvl_raw = attempt_or_dict.get("assessed_level", None)
        answers = attempt_or_dict.get("answers") or attempt_or_dict.get("submitted_answers") or []
        cand_id = attempt_or_dict.get("candidate_id")
        attempt_id = attempt_or_dict.get("attempt_id")
        user_id = attempt_or_dict.get("user_id")
    else:
        skill_name = str(getattr(attempt_or_dict, "skill", "")).strip()
        req_lvl_raw = getattr(attempt_or_dict, "required_level", "basic")
        assessed_lvl_raw = getattr(attempt_or_dict, "assessed_level", None)
        answers = getattr(attempt_or_dict, "answers", None) or getattr(attempt_or_dict, "submitted_answers", None) or []
        cand_id = getattr(attempt_or_dict, "candidate_id", None)
        attempt_id = getattr(attempt_or_dict, "attempt_id", None)
        user_id = getattr(attempt_or_dict, "user_id", None)

    req_lvl = parse_level(req_lvl_raw, default=1)
    assessed_lvl = parse_level(assessed_lvl_raw, default=0)
    level_gap = max(0, req_lvl - assessed_lvl)

    score_dict = extract_skill_scores(attempt_or_dict)
    timing_dict, intervals = compute_timing_metrics(answers)

    feature_dict = {
        "skill": skill_name,
        "required_level": req_lvl,
        "assessed_level": assessed_lvl,
        "level_gap": level_gap,
        **score_dict,
        **timing_dict,
    }
    if cand_id is not None:
        feature_dict["candidate_id"] = cand_id
    if attempt_id is not None:
        feature_dict["attempt_id"] = attempt_id
    if user_id is not None:
        feature_dict["user_id"] = user_id

    return feature_dict, intervals


def build_weakness_features(
    attempts: List[Union[Dict[str, Any], Any]]
) -> List[Dict[str, Any]]:
    """
    Transforms candidate assessment attempts into ML-ready feature dictionaries.

    Parameters:
        attempts (list): List of assessment attempt dicts or AssessmentAttempt ORM objects.

    Returns:
        list of dicts: List of feature dictionaries, one dictionary per assessed skill,
                       containing exact fixed feature keys plus optional candidate metadata.
    """
    if not isinstance(attempts, list) or not attempts:
        return []

    per_skill_data: List[Dict[str, Any]] = []
    candidate_intervals: List[float] = []

    for attempt in attempts:
        skill_feats, intervals = extract_single_skill_features(attempt)
        per_skill_data.append(skill_feats)
        candidate_intervals.extend(intervals)

    # Compute candidate-level cross-skill context
    total_scores = [s["total_score"] for s in per_skill_data]
    gapped_count = sum(1 for s in per_skill_data if s["level_gap"] > 0)
    num_skills = len(per_skill_data)

    cand_avg_score = round(float(np.mean(total_scores)), 4) if num_skills > 0 else 0.0
    cand_score_std = round(float(np.std(total_scores)), 4) if num_skills > 1 else 0.0
    cand_below_req_ratio = round(float(gapped_count / num_skills), 4) if num_skills > 0 else 0.0

    if candidate_intervals:
        cand_avg_timing = round(float(np.mean(candidate_intervals)), 4)
    else:
        # Fallback to mean of per-skill avg_answer_time_seconds for skills with timing
        timed_skill_means = [s["avg_answer_time_seconds"] for s in per_skill_data if s["timed_questions_count"] > 0]
        if timed_skill_means:
            cand_avg_timing = round(float(np.mean(timed_skill_means)), 4)
        else:
            cand_avg_timing = 0.0

    # Assemble final fixed-key feature dictionaries
    output: List[Dict[str, Any]] = []
    for skill_feats in per_skill_data:
        record = {
            "skill": skill_feats["skill"],
            "required_level": skill_feats["required_level"],
            "assessed_level": skill_feats["assessed_level"],
            "level_gap": skill_feats["level_gap"],
            "basic_score": skill_feats["basic_score"],
            "intermediate_score": skill_feats["intermediate_score"],
            "advanced_score": skill_feats["advanced_score"],
            "total_score": skill_feats["total_score"],
            "questions_answered_count": skill_feats["questions_answered_count"],
            "avg_answer_time_seconds": skill_feats["avg_answer_time_seconds"],
            "answer_time_std_seconds": skill_feats["answer_time_std_seconds"],
            "min_answer_time_seconds": skill_feats["min_answer_time_seconds"],
            "max_answer_time_seconds": skill_feats["max_answer_time_seconds"],
            "timed_questions_count": skill_feats["timed_questions_count"],
            "candidate_avg_total_score": cand_avg_score,
            "candidate_score_std": cand_score_std,
            "candidate_below_requirement_ratio": cand_below_req_ratio,
            "candidate_avg_answer_time_seconds": cand_avg_timing,
        }
        for k in ("candidate_id", "attempt_id", "user_id"):
            if k in skill_feats:
                record[k] = skill_feats[k]
        output.append(record)

    return output
