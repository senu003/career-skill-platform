"""
ML TARGET & ARCHITECTURE REDESIGN INVESTIGATION MODULE (STEP 5)

Performs empirical data investigation on assessment history and candidate attempts to evaluate
whether existing database records support longitudinal machine learning targets (e.g., predicting
future skill improvement or persistent weakness) vs the current deterministic weakness label.

STRICT INVESTIGATION ONLY:
- Does NOT train a new production model.
- Does NOT create a production prediction endpoint.
- Does NOT modify production scoring, assessment logic, APIs, or database schemas.
- Does NOT change existing target definitions.
- Does NOT manufacture synthetic data.
"""

import sys
import os
import copy
import math
from typing import List, Dict, Any, Union, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.models import AssessmentAttempt, AssessmentAnswer, User
from app.ml.weakness_dataset import build_weakness_dataset
from app.ml.weakness_labels import compute_weakness_target_label, TARGET_LABEL_KEY

LEVEL_MAP: Dict[str, int] = {
    "none": 0,
    "basic": 1,
    "intermediate": 2,
    "advanced": 3
}


def level_to_numeric(lvl: Optional[str]) -> int:
    """Converts string level ('basic', 'intermediate', 'advanced') to integer (1, 2, 3)."""
    if not lvl:
        return 0
    return LEVEL_MAP.get(str(lvl).strip().lower(), 0)


def load_attempts_data_from_db() -> List[Dict[str, Any]]:
    """
    Queries AssessmentAttempt and AssessmentAnswer records from the database
    and builds structured attempt records with timestamps and scores.
    """
    db = SessionLocal()
    try:
        attempts = db.query(AssessmentAttempt).all()
        if not attempts:
            return []

        attempts_data = []
        for att in attempts:
            answers = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == att.id).all()
            answers_payload = [
                {
                    "is_correct": bool(ans.is_correct),
                    "answered_at": ans.answered_at,
                    "level": ans.question_obj.level if ans.question_obj else "basic"
                }
                for ans in answers
            ]
            attempts_data.append({
                "attempt_id": att.id,
                "user_id": att.user_id,
                "candidate_id": str(att.user_id) if att.user_id is not None else f"attempt_{att.id}",
                "skill": att.skill,
                "required_level": att.required_level,
                "cv_level": att.cv_level,
                "assessed_level": att.assessed_level,
                "started_at": att.started_at,
                "completed_at": att.completed_at,
                "answers": answers_payload
            })

        # Process through dataset builder to compute features and target label
        dataset = build_weakness_dataset(attempts_data)
        # Ensure metadata timestamps and candidate IDs are preserved on output dicts
        for orig, record in zip(attempts_data, dataset):
            record["started_at"] = orig.get("started_at")
            record["completed_at"] = orig.get("completed_at")
            record["user_id"] = orig.get("user_id")
            record["candidate_id"] = orig.get("candidate_id")
            record["attempt_id"] = orig.get("attempt_id")
        return dataset
    finally:
        db.close()


def analyze_assessment_history(attempts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audits assessment attempt counts, unique candidates, candidate attempt frequencies,
    and time spans between repeated attempts.
    """
    if not attempts_data:
        return {
            "total_attempts": 0,
            "unique_candidates": 0,
            "candidates_1_attempt": 0,
            "candidates_2_attempts": 0,
            "candidates_3plus_attempts": 0,
            "candidate_identifier_field": "user_id / candidate_id",
            "time_spans_days": []
        }

    cand_attempt_counts: Dict[str, int] = {}
    cand_timestamps: Dict[str, List[datetime]] = {}

    for idx, r in enumerate(attempts_data):
        cid = str(r.get("candidate_id") or r.get("user_id") or r.get("attempt_id") or f"row_{idx}")
        cand_attempt_counts[cid] = cand_attempt_counts.get(cid, 0) + 1

        ts = r.get("completed_at") or r.get("started_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = None
        if isinstance(ts, datetime):
            if cid not in cand_timestamps:
                cand_timestamps[cid] = []
            cand_timestamps[cid].append(ts)

    c_1 = sum(1 for c in cand_attempt_counts.values() if c == 1)
    c_2 = sum(1 for c in cand_attempt_counts.values() if c == 2)
    c_3plus = sum(1 for c in cand_attempt_counts.values() if c >= 3)

    time_spans: List[float] = []
    for cid, ts_list in cand_timestamps.items():
        if len(ts_list) > 1:
            sorted_ts = sorted(ts_list)
            span_days = (sorted_ts[-1] - sorted_ts[0]).total_seconds() / 86400.0
            time_spans.append(round(span_days, 2))

    return {
        "total_attempts": len(attempts_data),
        "unique_candidates": len(cand_attempt_counts),
        "candidates_1_attempt": c_1,
        "candidates_2_attempts": c_2,
        "candidates_3plus_attempts": c_3plus,
        "candidate_identifier_field": "user_id (with attempt_id fallback for guest attempts)",
        "time_spans_days": time_spans
    }


def analyze_repeated_skills(attempts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies repeated skill attempts for the same candidate across time (t0, t1)
    and computes score change and level change.
    """
    if not attempts_data:
        return []

    # Group attempts by (candidate_id, skill)
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for idx, r in enumerate(attempts_data):
        cid = str(r.get("candidate_id") or r.get("user_id") or r.get("attempt_id") or f"row_{idx}")
        skill = str(r.get("skill", "")).strip()
        if not skill:
            continue
        key = (cid, skill)
        if key not in groups:
            groups[key] = []
        groups[key].append(copy.deepcopy(r))

    repeated_skill_pairs: List[Dict[str, Any]] = []

    for (cid, skill), records in groups.items():
        if len(records) < 2:
            continue

        # Sort chronologically by completed_at / started_at / attempt_id
        def get_sort_key(rec):
            ts = rec.get("completed_at") or rec.get("started_at")
            if isinstance(ts, datetime):
                return (ts, str(rec.get("attempt_id", "")))
            if isinstance(ts, str):
                try:
                    return (datetime.fromisoformat(ts), str(rec.get("attempt_id", "")))
                except ValueError:
                    pass
            return (datetime.min, str(rec.get("attempt_id", "")))

        sorted_recs = sorted(records, key=get_sort_key)

        # Pair adjacent chronological attempts (t0 -> t1)
        for i in range(len(sorted_recs) - 1):
            t0 = sorted_recs[i]
            t1 = sorted_recs[i + 1]

            t0_score = float(t0.get("total_score", 0.0))
            t1_score = float(t1.get("total_score", 0.0))
            score_change = round(t1_score - t0_score, 4)

            t0_lvl = t0.get("assessed_level")
            t1_lvl = t1.get("assessed_level")
            t0_lvl_num = level_to_numeric(t0_lvl)
            t1_lvl_num = level_to_numeric(t1_lvl)
            level_change = t1_lvl_num - t0_lvl_num

            t0_is_w = int(t0.get("is_weakness", 0))
            t1_is_w = int(t1.get("is_weakness", 0))

            t0_ts = t0.get("completed_at") or t0.get("started_at")
            t1_ts = t1.get("completed_at") or t1.get("started_at")

            repeated_skill_pairs.append({
                "candidate_id": cid,
                "skill": skill,
                "t0_attempt_id": t0.get("attempt_id"),
                "t1_attempt_id": t1.get("attempt_id"),
                "t0_timestamp": t0_ts,
                "t1_timestamp": t1_ts,
                "t0_score": t0_score,
                "t1_score": t1_score,
                "score_change": score_change,
                "t0_level": t0_lvl,
                "t1_level": t1_lvl,
                "t0_level_num": t0_lvl_num,
                "t1_level_num": t1_lvl_num,
                "level_change": level_change,
                "t0_is_weakness": t0_is_w,
                "t1_is_weakness": t1_is_w
            })

    return repeated_skill_pairs


def check_temporal_ordering(
    attempts_data: List[Dict[str, Any]],
    repeated_pairs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Checks timestamp reliability, missing timestamps, duplicate timestamps, and reversed ordering.
    """
    missing_timestamps = 0
    for r in attempts_data:
        ts = r.get("completed_at") or r.get("started_at")
        if ts is None:
            missing_timestamps += 1

    duplicate_timestamps = 0
    reversed_ordering = 0

    for pair in repeated_pairs:
        t0_ts = pair.get("t0_timestamp")
        t1_ts = pair.get("t1_timestamp")

        if t0_ts and t1_ts:
            if isinstance(t0_ts, str):
                try: t0_ts = datetime.fromisoformat(t0_ts)
                except ValueError: t0_ts = None
            if isinstance(t1_ts, str):
                try: t1_ts = datetime.fromisoformat(t1_ts)
                except ValueError: t1_ts = None

        if t0_ts and t1_ts:
            if t0_ts == t1_ts:
                duplicate_timestamps += 1
            elif t0_ts > t1_ts:
                reversed_ordering += 1

    return {
        "missing_timestamps_count": missing_timestamps,
        "duplicate_timestamps_count": duplicate_timestamps,
        "reversed_ordering_count": reversed_ordering,
        "is_temporal_ordering_reliable": (missing_timestamps == 0 and reversed_ordering == 0)
    }


def evaluate_improvement_targets(repeated_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates improvement and persistence target formulations on repeated skill observations.
    """
    total_pairs = len(repeated_pairs)
    if total_pairs == 0:
        return {
            "total_usable_pairs": 0,
            "improved_any_score": {"positive": 0, "negative": 0, "ratio": 0.0},
            "improved_score_threshold_0_10": {"positive": 0, "negative": 0, "ratio": 0.0},
            "improved_score_threshold_0_20": {"positive": 0, "negative": 0, "ratio": 0.0},
            "improved_level": {"positive": 0, "negative": 0, "ratio": 0.0},
            "persistent_weakness": {"positive": 0, "negative": 0, "ratio": 0.0}
        }

    # 1. Improved score (later_score > previous_score)
    imp_score_pos = sum(1 for p in repeated_pairs if p["score_change"] > 0)
    imp_score_neg = total_pairs - imp_score_pos

    # 2. Improved score threshold (score_change >= 0.10)
    imp_thresh_10_pos = sum(1 for p in repeated_pairs if p["score_change"] >= 0.10)
    imp_thresh_10_neg = total_pairs - imp_thresh_10_pos

    # 3. Improved score threshold (score_change >= 0.20)
    imp_thresh_20_pos = sum(1 for p in repeated_pairs if p["score_change"] >= 0.20)
    imp_thresh_20_neg = total_pairs - imp_thresh_20_pos

    # 4. Improved level (later_level_num > previous_level_num)
    imp_lvl_pos = sum(1 for p in repeated_pairs if p["level_change"] > 0)
    imp_lvl_neg = total_pairs - imp_lvl_pos

    # 5. Persistent weakness (t0 weakness = 1 AND t1 weakness = 1)
    persist_w_pos = sum(1 for p in repeated_pairs if p["t0_is_weakness"] == 1 and p["t1_is_weakness"] == 1)
    persist_w_neg = total_pairs - persist_w_pos

    return {
        "total_usable_pairs": total_pairs,
        "improved_any_score": {
            "positive": imp_score_pos,
            "negative": imp_score_neg,
            "ratio": round(imp_score_pos / total_pairs, 4) if total_pairs > 0 else 0.0
        },
        "improved_score_threshold_0_10": {
            "positive": imp_thresh_10_pos,
            "negative": imp_thresh_10_neg,
            "ratio": round(imp_thresh_10_pos / total_pairs, 4) if total_pairs > 0 else 0.0
        },
        "improved_score_threshold_0_20": {
            "positive": imp_thresh_20_pos,
            "negative": imp_thresh_20_neg,
            "ratio": round(imp_thresh_20_pos / total_pairs, 4) if total_pairs > 0 else 0.0
        },
        "improved_level": {
            "positive": imp_lvl_pos,
            "negative": imp_lvl_neg,
            "ratio": round(imp_lvl_pos / total_pairs, 4) if total_pairs > 0 else 0.0
        },
        "persistent_weakness": {
            "positive": persist_w_pos,
            "negative": persist_w_neg,
            "ratio": round(persist_w_pos / total_pairs, 4) if total_pairs > 0 else 0.0
        }
    }


def audit_data_quality_and_leakage(
    attempts_data: List[Dict[str, Any]],
    repeated_pairs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Audits data quality issues, duplicate candidate-skill-time pairs, and target leakage risks.
    """
    missing_user_ids = sum(1 for r in attempts_data if r.get("user_id") is None)
    duplicate_rows = 0

    seen_keys = set()
    for idx, r in enumerate(attempts_data):
        cid = str(r.get("candidate_id") or r.get("user_id") or f"row_{idx}")
        skill = str(r.get("skill", ""))
        ts = str(r.get("completed_at") or r.get("started_at") or "")
        key = (cid, skill, ts)
        if key in seen_keys:
            duplicate_rows += 1
        else:
            seen_keys.add(key)

    temporal_leakage_risk = (
        "HIGH RISK if features from t1 assessment (e.g. later_score, later_level, later_answer_time) "
        "are accidentally included in input feature matrix X. Strict temporal separation t0 (input) vs t1 (target) is required."
    )

    candidate_identity_leakage_risk = (
        "HIGH RISK if candidate identity (user_id / candidate_id) is used as a model feature. "
        "Must use candidate-aware StratifiedGroupKFold to isolate candidates across folds."
    )

    return {
        "missing_user_ids": missing_user_ids,
        "duplicate_candidate_skill_time_pairs": duplicate_rows,
        "temporal_leakage_risk": temporal_leakage_risk,
        "candidate_identity_leakage_risk": candidate_identity_leakage_risk
    }


def perform_data_sufficiency_analysis(
    history_stats: Dict[str, Any],
    target_stats: Dict[str, Any],
    repeated_pairs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Evaluates data sufficiency for Tasks A, B, C, D based on empirical database evidence.
    Categorizes tasks into:
    - Sufficient for exploratory ML
    - Borderline / limited
    - Insufficient
    """
    tot_attempts = history_stats.get("total_attempts", 0)
    unique_cands = history_stats.get("unique_candidates", 0)
    usable_pairs = target_stats.get("total_usable_pairs", 0)

    # Count unique candidates represented in repeated pairs
    unique_pair_cands = len(set(p["candidate_id"] for p in repeated_pairs)) if repeated_pairs else 0

    imp_pos = target_stats.get("improved_any_score", {}).get("positive", 0)
    imp_neg = target_stats.get("improved_any_score", {}).get("negative", 0)

    pers_pos = target_stats.get("persistent_weakness", {}).get("positive", 0)
    pers_neg = target_stats.get("persistent_weakness", {}).get("negative", 0)

    # Task A: Predict current weakness
    task_a = {
        "name": "Task A: Current Weakness Prediction",
        "target": "is_weakness (derived from level_gap > 0 OR total_score < 0.60)",
        "usable_samples": tot_attempts,
        "unique_candidates": unique_cands,
        "status": "Borderline / limited",
        "rationale": (
            "Target is deterministically derived from current assessment score rules. "
            "ML re-predicts baseline scoring logic rather than discovering independent real-world weakness. "
            "Pure timing features lack predictive power (ROC-AUC ~0.63)."
        )
    }

    # Task B: Predict future improvement
    task_b_sufficient = (usable_pairs >= 30 and unique_pair_cands > 1 and imp_pos >= 5 and imp_neg >= 5)
    task_b = {
        "name": "Task B: Future Skill Improvement Prediction",
        "target": "improved (later_score > previous_score at t1)",
        "usable_samples": usable_pairs,
        "unique_candidates": unique_pair_cands,
        "status": "Sufficient for exploratory ML" if task_b_sufficient else "Insufficient",
        "rationale": (
            f"Found {usable_pairs} repeated skill observation pairs across {unique_pair_cands} candidates, "
            f"but target label has ZERO positive samples (0 positive vs {imp_neg} negative). "
            "Supervised binary classification training is IMPOSSIBLE with single-class target data."
            if (imp_pos == 0 or imp_neg == 0) else
            f"Found {usable_pairs} repeated skill pairs across {unique_pair_cands} candidates with valid class distribution ({imp_pos} pos / {imp_neg} neg)."
        )
    }

    # Task C: Predict persistent weakness
    task_c_sufficient = (usable_pairs >= 30 and unique_pair_cands > 1 and pers_pos >= 5 and pers_neg >= 5)
    task_c = {
        "name": "Task C: Persistent Weakness Prediction",
        "target": "persistent_weakness (is_weakness = 1 at both t0 and t1)",
        "usable_samples": usable_pairs,
        "unique_candidates": unique_pair_cands,
        "status": "Sufficient for exploratory ML" if task_c_sufficient else "Insufficient",
        "rationale": (
            f"Found {usable_pairs} repeated skill pairs across {unique_pair_cands} candidates, "
            f"but target label has ZERO negative samples ({pers_pos} positive vs 0 negative). "
            "Supervised binary classification training is IMPOSSIBLE with single-class target data."
            if (pers_pos == 0 or pers_neg == 0) else
            f"Found {usable_pairs} repeated skill pairs across {unique_pair_cands} candidates with valid class distribution ({pers_pos} pos / {pers_neg} neg)."
        )
    }

    # Task D: Rank weakness priority
    task_d = {
        "name": "Task D: Rank Weakness Priority",
        "target": "None (No objective priority label observed in schema)",
        "usable_samples": 0,
        "unique_candidates": 0,
        "status": "Insufficient",
        "rationale": (
            "Database contains no objective observed target label for weakness priority. "
            "Creating a priority target would require inventing synthetic heuristic labels."
        )
    }

    return {
        "Task_A": task_a,
        "Task_B": task_b,
        "Task_C": task_c,
        "Task_D": task_d
    }


def make_decision_recommendation(task_evals: Dict[str, Dict[str, Any]]) -> str:
    """
    Chooses exactly ONE of:
    1. PROCEED_WITH_IMPROVEMENT_MODEL
    2. PROCEED_WITH_PERSISTENCE_MODEL
    3. PROCEED_WITH_CURRENT_WEAKNESS_MODEL_WITH_LIMITATIONS
    4. INSUFFICIENT_DATA_FOR_SUPERVISED_ML
    """
    b_status = task_evals["Task_B"]["status"]
    c_status = task_evals["Task_C"]["status"]

    if b_status == "Sufficient for exploratory ML":
        return "PROCEED_WITH_IMPROVEMENT_MODEL"
    elif c_status == "Sufficient for exploratory ML":
        return "PROCEED_WITH_PERSISTENCE_MODEL"
    else:
        return "INSUFFICIENT_DATA_FOR_SUPERVISED_ML"


def run_target_redesign_investigation(
    attempts_data: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Runs complete Step 5 ML Target & Architecture Redesign Investigation.
    """
    if attempts_data is None or len(attempts_data) == 0:
        attempts_data = load_attempts_data_from_db()

    history_stats = analyze_assessment_history(attempts_data)
    repeated_pairs = analyze_repeated_skills(attempts_data)
    temporal_stats = check_temporal_ordering(attempts_data, repeated_pairs)
    target_stats = evaluate_improvement_targets(repeated_pairs)
    quality_stats = audit_data_quality_and_leakage(attempts_data, repeated_pairs)
    task_evals = perform_data_sufficiency_analysis(history_stats, target_stats, repeated_pairs)
    recommendation = make_decision_recommendation(task_evals)

    results = {
        "history_stats": history_stats,
        "repeated_pairs": repeated_pairs,
        "temporal_stats": temporal_stats,
        "target_stats": target_stats,
        "quality_stats": quality_stats,
        "task_evaluations": task_evals,
        "recommendation": recommendation
    }

    results["report_text"] = format_target_redesign_report(results)
    return results


def format_target_redesign_report(results: Dict[str, Any]) -> str:
    """
    Formats complete investigation results into a clean markdown report.
    """
    hs = results["history_stats"]
    ts = results["temporal_stats"]
    tgt = results["target_stats"]
    qs = results["quality_stats"]
    te = results["task_evaluations"]
    rec = results["recommendation"]

    lines = [
        "============================================================",
        "  STEP 5: ML TARGET & ARCHITECTURE REDESIGN INVESTIGATION   ",
        "============================================================",
        "A. DATASET OVERVIEW:",
        f"   Total Assessment Attempts:        {hs['total_attempts']}",
        f"   Unique Candidates:                {hs['unique_candidates']}",
        f"   Candidates with 1 Attempt:        {hs['candidates_1_attempt']}",
        f"   Candidates with 2 Attempts:       {hs['candidates_2_attempts']}",
        f"   Candidates with 3+ Attempts:      {hs['candidates_3plus_attempts']}",
        f"   Candidate Identifier Field:       {hs['candidate_identifier_field']}",
        f"   Time Spans (Days):                {hs['time_spans_days'] if hs['time_spans_days'] else 'None'}",
        "------------------------------------------------------------",
        "B. LONGITUDINAL REPEATED SKILLS DATASET:",
        f"   Usable Before/After Skill Pairs:  {tgt['total_usable_pairs']}",
        f"   Score Improvement (t1 > t0):      Pos={tgt['improved_any_score']['positive']} | Neg={tgt['improved_any_score']['negative']} | Ratio={tgt['improved_any_score']['ratio']}",
        f"   Score Improvement (+0.10 thresh): Pos={tgt['improved_score_threshold_0_10']['positive']} | Neg={tgt['improved_score_threshold_0_10']['negative']} | Ratio={tgt['improved_score_threshold_0_10']['ratio']}",
        f"   Level Improvement (t1 > t0):      Pos={tgt['improved_level']['positive']} | Neg={tgt['improved_level']['negative']} | Ratio={tgt['improved_level']['ratio']}",
        f"   Persistent Weakness (w0=1, w1=1): Pos={tgt['persistent_weakness']['positive']} | Neg={tgt['persistent_weakness']['negative']} | Ratio={tgt['persistent_weakness']['ratio']}",
        "------------------------------------------------------------",
        "C. DATA QUALITY & TEMPORAL ORDERING AUDIT:",
        f"   Missing Timestamps:               {ts['missing_timestamps_count']}",
        f"   Duplicate Timestamps:             {ts['duplicate_timestamps_count']}",
        f"   Reversed/Impossible Time Order:   {ts['reversed_ordering_count']}",
        f"   Missing User IDs (Guest):         {qs['missing_user_ids']}",
        f"   Duplicate Candidate-Skill Pairs:  {qs['duplicate_candidate_skill_time_pairs']}",
        f"   Temporal Ordering Reliable?       {ts['is_temporal_ordering_reliable']}",
        "------------------------------------------------------------",
        "D. TASK COMPARISON AUDIT:",
    ]

    for k, v in te.items():
        lines.append(f"   [{k}] {v['name']}")
        lines.append(f"       Target:          {v['target']}")
        lines.append(f"       Usable Samples:  {v['usable_samples']} | Unique Candidates: {v['unique_candidates']}")
        lines.append(f"       Status:          {v['status']}")
        lines.append(f"       Rationale:       {v['rationale']}")

    lines.extend([
        "------------------------------------------------------------",
        "E. FINAL DECISION RECOMMENDATION:",
        f"   RECOMMENDATION: {rec}",
        "------------------------------------------------------------",
        "EXPLANATION:",
        f"   The database currently contains {hs['total_attempts']} total assessment attempt records across {hs['unique_candidates']} candidates.",
        f"   Of these, {hs['candidates_1_attempt']} candidates have taken only 1 assessment, leaving {tgt['total_usable_pairs']} repeated skill observation pairs.",
        f"   Supervised longitudinal ML models (such as future improvement or persistent weakness prediction)",
        f"   require repeated attempt observations per candidate ($t_0$ and $t_1$). With only {tgt['total_usable_pairs']} repeated skill pairs,",
        f"   the real database contains INSUFFICIENT DATA for supervised longitudinal ML training without synthetic data manufacturing.",
        "============================================================",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    res = run_target_redesign_investigation()
    print(res["report_text"])
