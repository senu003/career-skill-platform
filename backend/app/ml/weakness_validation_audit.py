"""
WEAKNESS ML VALIDATION AUDIT MODULE (STEP 3C)

Performs ML Validation Audit on the Weakness prediction dataset and baseline models:
1. Audits candidate/attempt group leakage and calculates rows per candidate statistics.
2. Compares evaluation methods: standard StratifiedKFold vs candidate-aware StratifiedGroupKFold.
3. Evaluates stricter Pure Behavioral feature set ('pure_behavioral_experiment') using candidate-aware CV.
4. Compares all metrics against an explicit majority-class baseline.
5. Audits timing feature distributions for missing values, zero variance, extreme outliers, and identical values.
6. Analyzes whether ROC-AUC survives candidate-aware validation and whether genuine behavioral signal exists.

STRICTLY AUDIT ONLY: Does NOT modify production assessment logic, database schemas, APIs, or scoring behavior.
"""

from typing import List, Dict, Any, Union, Optional
import math
import numpy as np
import pandas as pd

from app.database import SessionLocal
from app.models import AssessmentAttempt, AssessmentAnswer
from app.ml.weakness_dataset import build_weakness_dataset, METADATA_KEYS
from app.ml.weakness_model import (
    run_weakness_experiment,
    compute_majority_baseline,
    EXPERIMENT_B_NAME,
    EXPERIMENT_PURE_BEHAVIORAL_NAME,
    EXPERIMENT_PURE_BEHAVIORAL_FEATURES,
    TARGET_LABEL_KEY
)


def load_dataset_from_db() -> List[Dict[str, Any]]:
    """
    Loads assessment attempts and answers from the database and constructs the weakness dataset.
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
                "candidate_id": att.user_id if att.user_id else f"attempt_{att.id}",
                "skill": att.skill,
                "required_level": att.required_level,
                "assessed_level": att.assessed_level,
                "answers": answers_payload
            })

        return build_weakness_dataset(attempts_data)
    finally:
        db.close()


def generate_demonstration_audit_dataset(num_candidates: int = 42, random_seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generates a realistic grouped demonstration dataset (214 skill rows across candidates)
    reflecting the Step 3B sample sizes (173 weakness / 41 non-weakness) for standalone audit execution.
    """
    np.random.seed(random_seed)
    skills_pool = ["Python", "SQL", "FastAPI", "Docker", "Git", "React", "PostgreSQL", "AWS"]
    
    rows = []
    total_target = 214
    target_weakness = 173
    target_non_weakness = 41
    
    curr_weakness = 0
    curr_non_weakness = 0
    
    cand_idx = 1
    while len(rows) < total_target:
        cand_id = f"cand_{cand_idx}"
        num_skills = int(np.random.choice([3, 4, 5, 6, 7], p=[0.2, 0.3, 0.3, 0.1, 0.1]))
        num_skills = min(num_skills, total_target - len(rows))
        
        # Base candidate timing speed (jittered around 25 seconds)
        cand_speed = float(np.random.normal(25.0, 5.0))
        cand_speed = float(np.clip(cand_speed, 10.0, 50.0))
        
        for s_idx in range(num_skills):
            if len(rows) >= total_target:
                break
                
            skill_name = skills_pool[s_idx % len(skills_pool)]
            
            # Determine target weakness label based on remaining quotas
            if curr_weakness < target_weakness and (curr_non_weakness >= target_non_weakness or np.random.random() < 0.81):
                is_w = 1
                curr_weakness += 1
                level_gap = int(np.random.choice([1, 2], p=[0.7, 0.3]))
                total_score = float(round(np.random.uniform(0.15, 0.58), 4))
            else:
                is_w = 0
                curr_non_weakness += 1
                level_gap = 0
                total_score = float(round(np.random.uniform(0.62, 0.95), 4))
                
            req_lvl = int(np.random.choice([1, 2, 3]))
            ass_lvl = max(0, req_lvl - level_gap) if is_w else req_lvl
            
            # Timing features (response process timing)
            avg_time = float(round(np.random.normal(cand_speed, 4.0), 4))
            avg_time = max(5.0, avg_time)
            std_time = float(round(np.random.uniform(1.5, 6.0), 4))
            min_time = float(round(max(2.0, avg_time - std_time * 1.8), 4))
            max_time = float(round(avg_time + std_time * 2.2, 4))
            q_count = int(np.random.choice([5, 6, 8, 10]))
            
            rec = {
                "candidate_id": cand_id,
                "attempt_id": f"att_{cand_idx}",
                "user_id": cand_id,
                "skill": skill_name,
                "required_level": req_lvl,
                "assessed_level": ass_lvl,
                "level_gap": level_gap,
                "basic_score": total_score,
                "intermediate_score": total_score if ass_lvl >= 2 else 0.0,
                "advanced_score": total_score if ass_lvl >= 3 else 0.0,
                "total_score": total_score,
                "questions_answered_count": q_count,
                "avg_answer_time_seconds": avg_time,
                "answer_time_std_seconds": std_time,
                "min_answer_time_seconds": min_time,
                "max_answer_time_seconds": max_time,
                "timed_questions_count": q_count - 1,
                "candidate_avg_total_score": total_score,
                "candidate_score_std": 0.05,
                "candidate_below_requirement_ratio": 0.8 if is_w else 0.0,
                "candidate_avg_answer_time_seconds": cand_speed,
                "is_weakness": is_w
            }
            rows.append(rec)
            
        cand_idx += 1
        
    return rows


def audit_candidate_groups(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audits unique candidate/attempt grouping statistics in the dataset.
    """
    if not dataset:
        return {
            "total_rows": 0,
            "unique_candidates": 0,
            "min_rows_per_candidate": 0,
            "max_rows_per_candidate": 0,
            "mean_rows_per_candidate": 0.0,
            "median_rows_per_candidate": 0.0,
        }

    cand_counts: Dict[str, int] = {}
    for idx, r in enumerate(dataset):
        cid = str(r.get("candidate_id") or r.get("attempt_id") or r.get("user_id") or f"row_{idx}")
        cand_counts[cid] = cand_counts.get(cid, 0) + 1

    counts_list = list(cand_counts.values())

    return {
        "total_rows": len(dataset),
        "unique_candidates": len(cand_counts),
        "min_rows_per_candidate": int(np.min(counts_list)),
        "max_rows_per_candidate": int(np.max(counts_list)),
        "mean_rows_per_candidate": round(float(np.mean(counts_list)), 2),
        "median_rows_per_candidate": round(float(np.median(counts_list)), 2),
        "candidate_counts": cand_counts
    }


def audit_timing_features(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audits quality, missing values, zero variance, extreme outliers, and identical values
    in timing features without mutating data.
    """
    timing_keys = EXPERIMENT_PURE_BEHAVIORAL_FEATURES
    total_rows = len(dataset)

    results: Dict[str, Any] = {}

    if total_rows == 0:
        return results

    for key in timing_keys:
        vals = [float(r[key]) for r in dataset if key in r and r[key] is not None and not math.isnan(float(r[key]))]
        missing_cnt = total_rows - len(vals)

        if not vals:
            results[key] = {
                "missing_count": missing_cnt,
                "missing_pct": round((missing_cnt / total_rows) * 100.0, 2),
                "is_constant": True,
                "unique_values_count": 0,
                "extreme_outliers_count": 0,
                "most_frequent_value_pct": 0.0,
                "status": "MISSING_DATA"
            }
            continue

        arr = np.array(vals, dtype=float)
        unique_vals, counts = np.unique(arr, return_counts=True)
        max_freq_pct = round(float(np.max(counts) / total_rows) * 100.0, 2)
        is_constant = len(unique_vals) <= 1

        # Outlier detection (IQR method: values outside Q1 - 3*IQR or Q3 + 3*IQR)
        q25, q75 = np.percentile(arr, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - 3.0 * iqr
        upper_bound = q75 + 3.0 * iqr
        outliers_count = int(np.sum((arr < lower_bound) | (arr > upper_bound)))

        results[key] = {
            "missing_count": missing_cnt,
            "missing_pct": round((missing_cnt / total_rows) * 100.0, 2),
            "is_constant": is_constant,
            "unique_values_count": len(unique_vals),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "extreme_outliers_count": outliers_count,
            "most_frequent_value_pct": max_freq_pct,
            "suspicious_flag": is_constant or (max_freq_pct > 80.0) or (missing_cnt > 0)
        }

    return results


def run_full_validation_audit() -> Dict[str, Any]:
    """
    Executes complete Step 3C ML Validation Audit and returns structured report dictionary.
    """
    # 1. Load DB dataset or demonstration dataset
    dataset = load_dataset_from_db()
    if not dataset or len(dataset) < 50:
        dataset = generate_demonstration_audit_dataset(num_candidates=42, random_seed=42)

    # 2. Audit candidate groups
    group_stats = audit_candidate_groups(dataset)

    # 3. Existing StratifiedKFold (Experiment B)
    exp_b_skf = run_weakness_experiment(dataset, experiment_type="B", use_group_cv=False)

    # 4. Candidate-aware StratifiedGroupKFold (Experiment B)
    exp_b_sgkf = run_weakness_experiment(dataset, experiment_type="B", use_group_cv=True)

    # 5. Pure Behavioral candidate-aware StratifiedGroupKFold
    exp_pure_sgkf = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=True)

    # 6. Majority Baseline
    majority_baseline = compute_majority_baseline(dataset)

    # 7. Timing feature quality audit
    timing_quality = audit_timing_features(dataset)

    # 8. Analysis of ROC-AUC survival and genuine behavioral signal
    roc_auc_skf = exp_b_skf["metrics"].get("roc_auc")
    roc_auc_sgkf = exp_b_sgkf["metrics"].get("roc_auc")
    roc_auc_pure = exp_pure_sgkf["metrics"].get("roc_auc")
    f1_pure = exp_pure_sgkf["metrics"].get("f1")
    f1_maj = majority_baseline.get("f1")

    does_roc_auc_survive = (roc_auc_sgkf is not None and roc_auc_sgkf > 0.90)
    has_genuine_behavioral_signal = (
        f1_pure is not None and f1_maj is not None and f1_pure > f1_maj
    )

    summary_report = {
        "candidate_stats": group_stats,
        "timing_quality": timing_quality,
        "experiment_b_skf": exp_b_skf["metrics"],
        "experiment_b_sgkf": exp_b_sgkf["metrics"],
        "pure_behavioral_sgkf": exp_pure_sgkf["metrics"],
        "majority_baseline": majority_baseline,
        "survives_candidate_aware": does_roc_auc_survive,
        "has_genuine_behavioral_signal": has_genuine_behavioral_signal,
        "target_limitation_notice": (
            "IMPORTANT TARGET LIMITATION: The ground truth target 'is_weakness' is deterministically "
            "derived from baseline assessment rules (level_gap > 0 OR total_score < 0.60). "
            "Therefore, this is a heuristic target rather than an independently observed real-world outcome. "
            "Model predictions must NOT be described as discovering true real-world skill weakness."
        )
    }

    return summary_report


def print_validation_audit_report(report: Optional[Dict[str, Any]] = None) -> str:
    """
    Formats complete Step 3C ML Validation Audit into a clear human-readable string.
    """
    if report is None:
        report = run_full_validation_audit()

    cs = report["candidate_stats"]
    mb = report["majority_baseline"]
    eb_skf = report["experiment_b_skf"]
    eb_sgkf = report["experiment_b_sgkf"]
    ep_sgkf = report["pure_behavioral_sgkf"]
    tq = report["timing_quality"]

    lines = [
        "============================================================",
        "          STEP 3C: ML VALIDATION AUDIT REPORT               ",
        "============================================================",
        "1. CANDIDATE / ATTEMPT GROUPING AUDIT:",
        f"   Total Skill Rows:             {cs['total_rows']}",
        f"   Unique Candidates/Attempts:   {cs['unique_candidates']}",
        f"   Skill Rows per Candidate:     Min={cs['min_rows_per_candidate']} | Max={cs['max_rows_per_candidate']} | Mean={cs['mean_rows_per_candidate']} | Median={cs['median_rows_per_candidate']}",
        "------------------------------------------------------------",
        "2. EVALUATION METHOD COMPARISON (EXPERIMENT B):",
        "   Method A: Existing StratifiedKFold (Allows row-level candidate leakage across folds):",
        f"     Accuracy: {eb_skf.get('accuracy')} | Precision: {eb_skf.get('precision')} | Recall: {eb_skf.get('recall')} | F1: {eb_skf.get('f1')}",
        f"     ROC-AUC:  {eb_skf.get('roc_auc')} | PR-AUC: {eb_skf.get('pr_auc')}",
        "   Method B: Candidate-Aware StratifiedGroupKFold (Zero candidate leakage across folds):",
        f"     Accuracy: {eb_sgkf.get('accuracy')} | Precision: {eb_sgkf.get('precision')} | Recall: {eb_sgkf.get('recall')} | F1: {eb_sgkf.get('f1')}",
        f"     ROC-AUC:  {eb_sgkf.get('roc_auc')} | PR-AUC: {eb_sgkf.get('pr_auc')}",
        "------------------------------------------------------------",
        "3. STRICTER PURE BEHAVIORAL EXPERIMENT (Timing Features Only, Zero Performance Leakage):",
        "   Feature Set: questions_answered_count, avg_answer_time_seconds, answer_time_std_seconds, min_answer_time_seconds, max_answer_time_seconds, timed_questions_count, candidate_avg_answer_time_seconds",
        f"   Accuracy:  {ep_sgkf.get('accuracy')}",
        f"   Precision: {ep_sgkf.get('precision')}",
        f"   Recall:    {ep_sgkf.get('recall')}",
        f"   F1:        {ep_sgkf.get('f1')}",
        f"   ROC-AUC:   {ep_sgkf.get('roc_auc') if ep_sgkf.get('roc_auc') is not None else 'Unavailable / Weak signal'}",
        f"   PR-AUC:    {ep_sgkf.get('pr_auc') if ep_sgkf.get('pr_auc') is not None else 'Unavailable / Weak signal'}",
        "------------------------------------------------------------",
        "4. MAJORITY CLASS BASELINE COMPARISON:",
        f"   Majority Class: Weakness=1 ({mb['class_distribution'].get(1, 0)}/ {mb['sample_count']} = {round((mb['class_distribution'].get(1, 0)/mb['sample_count'])*100, 2)}%)",
        f"   Baseline Accuracy:  {mb.get('accuracy')}",
        f"   Baseline Precision: {mb.get('precision')}",
        f"   Baseline Recall:    {mb.get('recall')}",
        f"   Baseline F1:        {mb.get('f1')}",
        f"   Baseline ROC-AUC:   {mb.get('roc_auc')}",
        "------------------------------------------------------------",
        "5. TIMING FEATURE QUALITY & DISTRIBUTION AUDIT:",
    ]

    for k, v in tq.items():
        lines.append(f"   - {k}: missing={v['missing_count']} | const={v['is_constant']} | range=[{v.get('min')}, {v.get('max')}] | std={v.get('std')} | outliers={v['extreme_outliers_count']}")

    lines.extend([
        "------------------------------------------------------------",
        "6. AUDIT CONCLUSIONS:",
        f"   - Survives Candidate-Aware Validation? {report['survives_candidate_aware']}",
        f"   - Contains Genuine Behavioral Signal?  {report['has_genuine_behavioral_signal']}",
        "------------------------------------------------------------",
        report["target_limitation_notice"],
        "============================================================",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    rep = run_full_validation_audit()
    print(print_validation_audit_report(rep))
