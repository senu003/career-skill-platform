"""
CLEAN BEHAVIORAL EXPERIMENT MODULE (STEP 4B)

Evaluates whether candidate response timing contains genuine predictive signal
for the weakness label after removing structural question-volume shortcuts
(questions_answered_count, timed_questions_count, candidate_avg_answer_time_seconds)
and excluding unassessed skill rows lacking timing evidence.

STRICT EXPERIMENTATION ONLY:
- Does NOT integrate ML into production.
- Does NOT modify database schemas.
- Does NOT modify assessment scoring or API behavior.
- Does NOT modify Step 1/Step 2 target definition.
"""

import sys
import os
import copy
import math
from typing import List, Dict, Any, Union, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score
)

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.ml.weakness_dataset import build_weakness_dataset
from app.ml.weakness_validation_audit import (
    load_dataset_from_db,
    generate_demonstration_audit_dataset,
    audit_candidate_groups
)
from app.ml.weakness_model import (
    run_weakness_experiment,
    compute_majority_baseline,
    EXPERIMENT_PURE_BEHAVIORAL_FEATURES,
    TARGET_LABEL_KEY
)

# Clean behavioral experiment feature set: genuine timing/process features ONLY
CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES: List[str] = [
    "avg_answer_time_seconds",
    "answer_time_std_seconds",
    "min_answer_time_seconds",
    "max_answer_time_seconds",
]

# Explicit list of excluded features and rationale
EXCLUDED_FEATURES_RATIONALE: Dict[str, str] = {
    "questions_answered_count": "Structural shortcut / proxy for total_score = 0",
    "timed_questions_count": "Structural shortcut / proxy for total_score = 0",
    "candidate_avg_answer_time_seconds": "Constant value in baseline dataset (zero weight)",
    "level_gap": "Direct deterministic component of target definition (leakage)",
    "total_score": "Direct deterministic component of target definition (leakage)",
    "candidate_below_requirement_ratio": "Aggregated target proxy across skills",
    "required_level": "Assessment requirement level (not candidate behavior)",
    "assessed_level": "Direct component of level_gap (target leakage)",
    "basic_score": "Sub-score performance component (target leakage)",
    "intermediate_score": "Sub-score performance component (target leakage)",
    "advanced_score": "Sub-score performance component (target leakage)",
    "candidate_avg_total_score": "Aggregated candidate score (target leakage)",
    "candidate_score_std": "Aggregated candidate score variance (target leakage)"
}


def filter_clean_behavioral_dataset(
    dataset: List[Dict[str, Any]],
    target_key: str = TARGET_LABEL_KEY
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
    """
    Excludes unassessed skill rows lacking valid timing observations without mutating original dataset.
    Detects constant (zero-variance) features among remaining clean rows.

    Parameters:
        dataset: List of dataset dict records.
        target_key: Key name for target label.

    Returns:
        Tuple (clean_dataset, metadata_dict, active_features):
          - clean_dataset: List of filtered dict records with valid timing evidence.
          - metadata_dict: Dictionary reporting row exclusions, candidate counts, class distributions.
          - active_features: List of clean features excluding constant/zero-variance features.
    """
    if not dataset:
        return [], {
            "original_row_count": 0,
            "excluded_rows_count": 0,
            "final_clean_row_count": 0,
            "unique_candidates": 0,
            "class_distribution": {0: 0, 1: 0},
            "constant_features_excluded": []
        }, []

    clean_dataset: List[Dict[str, Any]] = []
    excluded_count = 0

    for record in dataset:
        q_ans = record.get("questions_answered_count", 0)
        t_ans = record.get("timed_questions_count", 0)
        avg_t = record.get("avg_answer_time_seconds")

        # Exclude if zero questions answered OR zero timed questions OR invalid/missing average timing
        is_unassessed = (
            q_ans == 0 or
            t_ans == 0 or
            avg_t is None or
            math.isnan(float(avg_t))
        )

        if is_unassessed:
            excluded_count += 1
        else:
            clean_dataset.append(copy.deepcopy(record))

    original_count = len(dataset)
    final_count = len(clean_dataset)

    # Count candidates / attempts in clean dataset
    cand_ids = set()
    class_dist = {0: 0, 1: 0}
    for r in clean_dataset:
        cid = str(r.get("candidate_id") or r.get("attempt_id") or r.get("user_id") or "unknown")
        cand_ids.add(cid)
        lbl = int(r.get(target_key, 0))
        class_dist[lbl] = class_dist.get(lbl, 0) + 1

    # Detect zero-variance (constant) features in clean dataset
    active_features: List[str] = []
    constant_features: List[str] = []

    if final_count > 0:
        for feat in CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES:
            vals = [float(r[feat]) for r in clean_dataset if feat in r and r[feat] is not None]
            if not vals:
                constant_features.append(feat)
            else:
                std_v = float(np.std(vals))
                min_v = float(np.min(vals))
                max_v = float(np.max(vals))
                if std_v == 0.0 or min_v == max_v:
                    constant_features.append(feat)
                else:
                    active_features.append(feat)

    metadata_dict = {
        "original_row_count": original_count,
        "excluded_rows_count": excluded_count,
        "final_clean_row_count": final_count,
        "unique_candidates": len(cand_ids),
        "class_distribution": class_dist,
        "constant_features_excluded": constant_features
    }

    return clean_dataset, metadata_dict, active_features


def compute_clean_descriptive_stats(
    clean_dataset: List[Dict[str, Any]],
    features: List[str],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Any]:
    """
    Computes descriptive timing statistics (count, mean, median, std, min, max)
    separated by target label (is_weakness = 0 vs is_weakness = 1).
    """
    g0_records = [r for r in clean_dataset if target_key in r and int(r[target_key]) == 0]
    g1_records = [r for r in clean_dataset if target_key in r and int(r[target_key]) == 1]

    stats: Dict[str, Any] = {}

    def _calc_stats(records: List[Dict[str, Any]], feat: str) -> Dict[str, Any]:
        vals = [float(r[feat]) for r in records if feat in r and r[feat] is not None and not math.isnan(float(r[feat]))]
        if not vals:
            return {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        arr = np.array(vals, dtype=float)
        return {
            "count": len(vals),
            "mean": round(float(np.mean(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4)
        }

    for f in features:
        stats[f] = {
            "is_weakness_0": _calc_stats(g0_records, f),
            "is_weakness_1": _calc_stats(g1_records, f)
        }

    return stats


def run_clean_behavioral_experiment(
    dataset: Optional[List[Dict[str, Any]]] = None,
    random_state: int = 42
) -> Dict[str, Any]:
    """
    Executes Step 4B Clean Behavioral Dataset Experiment:
    1. Filters out unassessed rows lacking timing evidence.
    2. Detects and removes constant features.
    3. Fits StandardScaler + LogisticRegression(L2) with Candidate-Aware StratifiedGroupKFold.
    4. Evaluates metrics (Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC).
    5. Compares against Majority Baseline and Previous Pure Behavioral Experiment.
    6. Returns complete structured experiment report.
    """
    if dataset is None or len(dataset) == 0:
        dataset = load_dataset_from_db()
        if not dataset or len(dataset) < 50:
            dataset = generate_demonstration_audit_dataset(num_candidates=42, random_seed=random_state)

    # 1. Filter clean dataset and handle constant features
    clean_dataset, metadata, active_features = filter_clean_behavioral_dataset(dataset)

    # 2. Compute descriptive statistics
    descriptive_stats = compute_clean_descriptive_stats(clean_dataset, active_features)

    # Check class sufficiency for exploratory CV
    g0_count = metadata["class_distribution"].get(0, 0)
    g1_count = metadata["class_distribution"].get(1, 0)
    sufficient_classes = (g0_count >= 5 and g1_count >= 5)

    # 3. Previous Pure Behavioral Experiment (Step 3C/4A with volume features) on full dataset
    try:
        previous_exp_results = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=True)
    except Exception as e:
        previous_exp_results = {"metrics": {"accuracy": None, "precision": None, "recall": None, "f1": None, "roc_auc": None, "pr_auc": None}}

    # 4. Clean Majority Baseline on clean dataset
    clean_majority_baseline = compute_majority_baseline(clean_dataset)

    # 5. Clean Behavioral Model Training & Evaluation
    clean_metrics: Dict[str, Any] = {
        "accuracy": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "roc_auc": None,
        "pr_auc": None
    }
    trained_model = None

    if len(clean_dataset) >= 10 and len(active_features) > 0 and sufficient_classes:
        X_mat = np.array([[float(r[f]) for f in active_features] for r in clean_dataset], dtype=float)
        y_vec = np.array([int(r[TARGET_LABEL_KEY]) for r in clean_dataset], dtype=int)
        groups = np.array([str(r.get("candidate_id") or r.get("attempt_id") or r.get("user_id") or f"row_{idx}")
                          for idx, r in enumerate(clean_dataset)])

        unique_groups = np.unique(groups)
        n_splits = min(5, len(unique_groups), min(g0_count, g1_count))

        if n_splits >= 2:
            sgkf = StratifiedGroupKFold(n_splits=n_splits)
            y_preds = np.zeros(len(y_vec))
            y_probs = np.zeros(len(y_vec))

            for train_idx, val_idx in sgkf.split(X_mat, y_vec, groups):
                X_tr, y_tr = X_mat[train_idx], y_vec[train_idx]
                X_va = X_mat[val_idx]

                pipe = Pipeline([
                    ("scaler", StandardScaler()),
                    ("classifier", LogisticRegression(C=1.0, random_state=random_state, max_iter=1000))
                ])
                pipe.fit(X_tr, y_tr)

                y_preds[val_idx] = pipe.predict(X_va)
                if hasattr(pipe, "predict_proba"):
                    y_probs[val_idx] = pipe.predict_proba(X_va)[:, 1]

            # Fit final model on full clean dataset for object inspection
            final_pipe = Pipeline([
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(C=1.0, random_state=random_state, max_iter=1000))
            ])
            final_pipe.fit(X_mat, y_vec)
            trained_model = final_pipe

            clean_metrics = {
                "accuracy": round(float(accuracy_score(y_vec, y_preds)), 4),
                "precision": round(float(precision_score(y_vec, y_preds, zero_division=0)), 4),
                "recall": round(float(recall_score(y_vec, y_preds, zero_division=0)), 4),
                "f1": round(float(f1_score(y_vec, y_preds, zero_division=0)), 4),
                "roc_auc": round(float(roc_auc_score(y_vec, y_probs)), 4) if len(np.unique(y_vec)) > 1 else None,
                "pr_auc": round(float(average_precision_score(y_vec, y_probs)), 4) if len(np.unique(y_vec)) > 1 else None
            }
        else:
            # Fallback for small clean datasets
            pipe = Pipeline([
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(C=1.0, random_state=random_state, max_iter=1000))
            ])
            pipe.fit(X_mat, y_vec)
            trained_model = pipe
            preds = pipe.predict(X_mat)
            probs = pipe.predict_proba(X_mat)[:, 1] if hasattr(pipe, "predict_proba") else preds

            clean_metrics = {
                "accuracy": round(float(accuracy_score(y_vec, preds)), 4),
                "precision": round(float(precision_score(y_vec, preds, zero_division=0)), 4),
                "recall": round(float(recall_score(y_vec, preds, zero_division=0)), 4),
                "f1": round(float(f1_score(y_vec, preds, zero_division=0)), 4),
                "roc_auc": round(float(roc_auc_score(y_vec, probs)), 4) if len(np.unique(y_vec)) > 1 else None,
                "pr_auc": round(float(average_precision_score(y_vec, probs)), 4) if len(np.unique(y_vec)) > 1 else None
            }

    # 6. Signal evaluation conclusion
    # Compare clean model F1/ROC-AUC against majority baseline
    clean_f1 = clean_metrics.get("f1")
    maj_f1 = clean_majority_baseline.get("f1")
    clean_roc = clean_metrics.get("roc_auc")

    if clean_roc is not None and clean_roc >= 0.70 and clean_f1 is not None and maj_f1 is not None and clean_f1 > (maj_f1 + 0.10):
        signal_outcome = "A. Strong signal remains"
        signal_explanation = "Clean response-timing features demonstrate substantial predictive signal beyond baseline."
    elif clean_roc is not None and clean_roc >= 0.55 and clean_f1 is not None and maj_f1 is not None and clean_f1 > maj_f1:
        signal_outcome = "B. Moderate signal remains"
        signal_explanation = "Clean response-timing features show slight/moderate association with heuristic weakness label."
    else:
        signal_outcome = "C. Little/no useful signal remains"
        signal_explanation = (
            "After excluding question-volume shortcuts and unassessed rows, pure response-timing features "
            "provide little or no useful predictive signal beyond the majority baseline (ROC-AUC ~0.50)."
        )

    results = {
        "metadata": metadata,
        "active_features": active_features,
        "excluded_features_rationale": EXCLUDED_FEATURES_RATIONALE,
        "descriptive_stats": descriptive_stats,
        "sufficient_classes_for_cv": sufficient_classes,
        "clean_majority_baseline": clean_majority_baseline,
        "previous_pure_behavioral_metrics": previous_exp_results.get("metrics", {}),
        "clean_behavioral_metrics": clean_metrics,
        "signal_outcome": signal_outcome,
        "signal_explanation": signal_explanation,
        "trained_model": trained_model,
        "target_limitation_notice": (
            "IMPORTANT TARGET EVALUATION NOTICE: These metrics evaluate alignment with the baseline assessment "
            "heuristic target (level_gap > 0 OR total_score < 0.60), NOT real-world skill weakness."
        )
    }

    results["report_text"] = format_clean_experiment_report(results)
    return results


def format_clean_experiment_report(results: Dict[str, Any]) -> str:
    """
    Formats the Step 4B Clean Behavioral Experiment results into a clear text report.
    """
    meta = results["metadata"]
    cm = results["clean_behavioral_metrics"]
    pm = results["previous_pure_behavioral_metrics"]
    mb = results["clean_majority_baseline"]
    stats = results["descriptive_stats"]

    lines = [
        "============================================================",
        "     STEP 4B: CLEAN BEHAVIORAL EXPERIMENT REPORT            ",
        "============================================================",
        "1. DATASET FILTERING & UNASSESSED ROWS EXCLUSION:",
        f"   Original Total Skill Rows:            {meta['original_row_count']}",
        f"   Excluded Rows (No Timing Evidence):   {meta['excluded_rows_count']}",
        f"   Final Clean Skill Rows:               {meta['final_clean_row_count']}",
        f"   Remaining Unique Candidates/Attempts: {meta['unique_candidates']}",
        f"   Clean Class Distribution:             Weakness=0: {meta['class_distribution'].get(0, 0)} | Weakness=1: {meta['class_distribution'].get(1, 0)}",
        "------------------------------------------------------------",
        "2. FEATURE INCLUSION & EXCLUSION AUDIT:",
        f"   Features Requested: {', '.join(CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES)}",
        f"   Features Actually Used: {', '.join(results['active_features']) if results['active_features'] else 'None'}",
        f"   Constant Features Excluded: {', '.join(meta['constant_features_excluded']) if meta['constant_features_excluded'] else 'None'}",
        "   Removed Shortcut/Leakage Features:",
    ]

    for feat, rat in EXCLUDED_FEATURES_RATIONALE.items():
        lines.append(f"     - {feat:34s}: {rat}")

    lines.extend([
        "------------------------------------------------------------",
        "3. EXPERIMENT METRICS COMPARISON REPORT:",
        "   [A] Clean Majority Baseline (Clean Dataset):",
        f"       Accuracy:  {mb.get('accuracy')} | Precision: {mb.get('precision')} | Recall: {mb.get('recall')} | F1: {mb.get('f1')} | ROC-AUC: {mb.get('roc_auc')}",
        "   [B] Previous Pure Behavioral Experiment (Step 3C/4A - Includes Volume Shortcuts):",
        f"       Accuracy:  {pm.get('accuracy')} | Precision: {pm.get('precision')} | Recall: {pm.get('recall')} | F1: {pm.get('f1')} | ROC-AUC: {pm.get('roc_auc')}",
        "   [C] New Clean Behavioral Experiment (Step 4B - Genuine Timing Only):",
        f"       Accuracy:  {cm.get('accuracy')} | Precision: {cm.get('precision')} | Recall: {cm.get('recall')} | F1: {cm.get('f1')} | ROC-AUC: {cm.get('roc_auc')} | PR-AUC: {cm.get('pr_auc')}",
        "------------------------------------------------------------",
        "4. CORE INVESTIGATION ANSWER:",
        f"   Outcome:     {results['signal_outcome']}",
        f"   Explanation: {results['signal_explanation']}",
        "------------------------------------------------------------",
        "5. DESCRIPTIVE TIMING DISTRIBUTIONS BY TARGET (CLEAN DATASET):",
    ])

    for f_name, f_stats in stats.items():
        g0 = f_stats.get("is_weakness_0", {})
        g1 = f_stats.get("is_weakness_1", {})
        lines.append(f"   Feature: {f_name}")
        lines.append(
            f"     is_weakness=0 (n={g0.get('count')}): mean={g0.get('mean')}, median={g0.get('median')}, std={g0.get('std')}, range=[{g0.get('min')}, {g0.get('max')}]"
        )
        lines.append(
            f"     is_weakness=1 (n={g1.get('count')}): mean={g1.get('mean')}, median={g1.get('median')}, std={g1.get('std')}, range=[{g1.get('min')}, {g1.get('max')}]"
        )

    lines.extend([
        "------------------------------------------------------------",
        results["target_limitation_notice"],
        "============================================================",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    res = run_clean_behavioral_experiment()
    print(res["report_text"])
