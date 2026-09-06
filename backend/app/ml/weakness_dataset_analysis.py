"""
WEAKNESS ML DATASET QUALITY & LEAKAGE ANALYSIS MODULE

Inspects the dataset produced by build_weakness_dataset to evaluate dataset quality,
class balance, feature statistics, missing values, duplicates, and target leakage risks.

Strictly diagnostic only. Does NOT train models, manufacture synthetic data, or mutate
input datasets or existing assessment scoring/database logic.
"""

from typing import List, Dict, Any, Union, Optional
import math
import numpy as np
import pandas as pd

from app.ml.weakness_dataset import METADATA_KEYS, NUMERICAL_FEATURE_KEYS
from app.ml.weakness_features import FEATURE_KEYS
from app.ml.weakness_labels import TARGET_LABEL_KEY, WEAKNESS_SCORE_THRESHOLD

# Known primary target-defining features that cause direct target leakage in baseline rule
PRIMARY_LEAKAGE_FEATURES = ["level_gap", "total_score"]

# Secondary features derived from or directly used in calculating target-defining variables
SECONDARY_LEAKAGE_FEATURES = [
    "assessed_level",
    "required_level",
    "candidate_below_requirement_ratio",
    "basic_score",
    "intermediate_score",
    "advanced_score",
]


def _is_missing(val: Any) -> bool:
    """Checks if a value is None, NaN, or missing."""
    if val is None:
        return True
    if isinstance(val, (float, np.floating)) and (math.isnan(val) or np.isnan(val)):
        return True
    return False


def detect_target_leakage(
    dataset: List[Dict[str, Any]],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Any]:
    """
    Explicitly analyzes target leakage risks and deterministic target relationships.

    Parameters:
        dataset (list of dicts): Clean dataset records.
        target_key (str): Key name for the target label.

    Returns:
        dict containing flagged leakage features and empirical relationship details.
    """
    flagged_features: List[str] = []
    leakage_reasons: Dict[str, str] = {}
    empirical_perfect_predictors: List[str] = []

    # 1. Always flag known target-defining primary leakage features
    for feat in PRIMARY_LEAKAGE_FEATURES:
        flagged_features.append(feat)
        leakage_reasons[feat] = (
            f"Primary Target Leakage: '{feat}' is explicitly used in the baseline target rule "
            f"(is_weakness = 1 if level_gap > 0 OR total_score < {WEAKNESS_SCORE_THRESHOLD})."
        )

    # 2. Flag secondary derived leakage features
    for feat in SECONDARY_LEAKAGE_FEATURES:
        if feat not in flagged_features:
            flagged_features.append(feat)
            leakage_reasons[feat] = (
                f"Secondary Target Leakage: '{feat}' is directly derived from or used to calculate "
                f"the target-defining variables level_gap or total_score."
            )

    # 3. Empirical check for suspicious direct relationships with target across dataset
    if dataset:
        target_vals = [int(r.get(target_key, 0)) for r in dataset if target_key in r]
        all_keys = list(FEATURE_KEYS)

        for feat in all_keys:
            if feat in METADATA_KEYS:
                continue
            
            feat_vals = []
            valid_targets = []
            for r in dataset:
                v = r.get(feat)
                t = r.get(target_key)
                if not _is_missing(v) and t is not None:
                    feat_vals.append(float(v))
                    valid_targets.append(int(t))

            if not feat_vals or len(set(valid_targets)) <= 1:
                continue

            # Check if feature value perfectly separates target
            # e.g., if level_gap > 0 always predicts weakness = 1
            if feat == "level_gap":
                deterministic_match = all(
                    (v > 0 and t == 1) or (v == 0)
                    for v, t in zip(feat_vals, valid_targets)
                )
                if deterministic_match:
                    empirical_perfect_predictors.append(feat)

            elif feat == "total_score":
                deterministic_match = all(
                    (v < WEAKNESS_SCORE_THRESHOLD and t == 1) or (v >= WEAKNESS_SCORE_THRESHOLD)
                    for v, t in zip(feat_vals, valid_targets)
                )
                if deterministic_match:
                    empirical_perfect_predictors.append(feat)

    return {
        "flagged_leakage_features": flagged_features,
        "leakage_reasons": leakage_reasons,
        "empirical_perfect_predictors": empirical_perfect_predictors,
        "summary": (
            "Target leakage risks identified. 'level_gap' and 'total_score' deterministically "
            "define the baseline ground-truth target. These must be handled or excluded during "
            "ML model training to prevent trivial 100% accurate shortcut learning."
        )
    }


def analyze_weakness_dataset(
    dataset: Union[List[Dict[str, Any]], pd.DataFrame],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Any]:
    """
    Analyzes dataset quality, feature distributions, missing values, duplicates,
    and target leakage risks without mutating the input dataset.

    Parameters:
        dataset (list of dicts or pd.DataFrame): Dataset produced by build_weakness_dataset.
        target_key (str): Name of target label key. Default "is_weakness".

    Returns:
        dict: Complete dataset quality & leakage report.
    """
    # 1. Convert DataFrame to list of dicts safely without mutating input
    if isinstance(dataset, pd.DataFrame):
        records = dataset.to_dict(orient="records")
    elif isinstance(dataset, list):
        records = [r.copy() for r in dataset]
    else:
        records = []

    row_count = len(records)

    # Empty dataset handling
    if row_count == 0:
        return {
            "row_count": 0,
            "unique_skill_count": 0,
            "class_distribution": {"weakness": 0, "non_weakness": 0},
            "weakness_percentage": 0.0,
            "class_balance_ratio": 0.0,
            "missing_values": {},
            "duplicate_rows": 0,
            "duplicate_feature_rows": 0,
            "constant_features": [],
            "numeric_ranges": {},
            "target_leakage_risks": PRIMARY_LEAKAGE_FEATURES + SECONDARY_LEAKAGE_FEATURES,
            "target_leakage_details": detect_target_leakage([], target_key=target_key),
            "dataset_sufficiency": {
                "is_sufficient_for_ml": False,
                "reason": "Dataset is empty (0 rows).",
                "sample_size": 0,
                "min_recommended_samples": 50,
            }
        }

    # 2. Extract skills metadata
    unique_skills = set(str(r.get("skill", "")).strip() for r in records if "skill" in r and r.get("skill"))
    unique_skill_count = len(unique_skills)

    # 3. Class distribution
    weakness_count = sum(1 for r in records if int(r.get(target_key, 0)) == 1)
    non_weakness_count = sum(1 for r in records if int(r.get(target_key, 0)) == 0)
    weakness_pct = round((weakness_count / row_count) * 100.0, 2)

    if weakness_count > 0 and non_weakness_count > 0:
        class_balance_ratio = round(min(weakness_count, non_weakness_count) / max(weakness_count, non_weakness_count), 4)
    else:
        class_balance_ratio = 0.0

    # 4. Determine all feature keys present
    all_keys = list(FEATURE_KEYS)
    if target_key not in all_keys:
        all_keys.append(target_key)

    # 5. Missing values count per feature
    missing_values: Dict[str, int] = {}
    for key in all_keys:
        missing_count = sum(1 for r in records if key not in r or _is_missing(r[key]))
        missing_values[key] = missing_count

    # 6. Duplicate row detection
    # Full duplicate rows (all key-value pairs)
    serialized_full = [tuple(sorted((k, str(v)) for k, v in r.items())) for r in records]
    duplicate_rows = row_count - len(set(serialized_full))

    # Duplicate feature vectors (excluding metadata 'skill' and target)
    serialized_features = [
        tuple(sorted((k, str(v)) for k, v in r.items() if k not in METADATA_KEYS and k != target_key))
        for r in records
    ]
    duplicate_feature_rows = row_count - len(set(serialized_features))

    # 7. Constant feature detection (features with only 1 unique value)
    constant_features: List[str] = []
    numeric_ranges: Dict[str, Dict[str, float]] = {}

    for key in FEATURE_KEYS:
        if key in METADATA_KEYS:
            continue

        vals = [float(r[key]) for r in records if key in r and not _is_missing(r[key])]
        if not vals:
            continue

        unique_vals = set(vals)
        if len(unique_vals) <= 1 and row_count > 1:
            constant_features.append(key)

        # Numeric ranges
        n_arr = np.array(vals, dtype=float)
        numeric_ranges[key] = {
            "min": round(float(np.min(n_arr)), 4),
            "max": round(float(np.max(n_arr)), 4),
            "mean": round(float(np.mean(n_arr)), 4),
            "std": round(float(np.std(n_arr)), 4),
        }

    # 8. Target leakage analysis
    leakage_details = detect_target_leakage(records, target_key=target_key)
    target_leakage_risks = leakage_details["flagged_leakage_features"]

    # 9. Dataset sufficiency assessment
    is_sufficient = (row_count >= 50) and (weakness_count >= 10) and (non_weakness_count >= 10)
    if row_count < 50:
        sufficiency_reason = (
            f"Dataset size ({row_count} rows) is below the minimum recommended sample size (50 rows) "
            f"for reliable machine learning model training and evaluation."
        )
    elif weakness_count < 10 or non_weakness_count < 10:
        sufficiency_reason = (
            f"Severe class imbalance ({weakness_count} weakness vs {non_weakness_count} non-weakness). "
            f"At least 10 samples per class are required for cross-validation."
        )
    else:
        sufficiency_reason = "Dataset size and class balance appear sufficient for baseline ML training."

    sufficiency = {
        "is_sufficient_for_ml": is_sufficient,
        "reason": sufficiency_reason,
        "sample_size": row_count,
        "min_recommended_samples": 50,
    }

    return {
        "row_count": row_count,
        "unique_skill_count": unique_skill_count,
        "class_distribution": {
            "weakness": weakness_count,
            "non_weakness": non_weakness_count,
        },
        "weakness_percentage": weakness_pct,
        "class_balance_ratio": class_balance_ratio,
        "missing_values": missing_values,
        "duplicate_rows": duplicate_rows,
        "duplicate_feature_rows": duplicate_feature_rows,
        "constant_features": constant_features,
        "numeric_ranges": numeric_ranges,
        "target_leakage_risks": target_leakage_risks,
        "target_leakage_details": leakage_details,
        "dataset_sufficiency": sufficiency,
    }


def print_weakness_dataset_report(
    report_or_dataset: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]
) -> str:
    """
    Formats the dataset analysis report into a clean readable string report.
    """
    if isinstance(report_or_dataset, dict) and "row_count" in report_or_dataset:
        report = report_or_dataset
    else:
        report = analyze_weakness_dataset(report_or_dataset)

    lines = [
        "============================================================",
        "          WEAKNESS ML DATASET ANALYSIS REPORT              ",
        "============================================================",
        f"Total Rows:                {report['row_count']}",
        f"Unique Skills Count:       {report['unique_skill_count']}",
        f"Class Distribution:        Weakness (1): {report['class_distribution']['weakness']} | Non-Weakness (0): {report['class_distribution']['non_weakness']}",
        f"Weakness Percentage:       {report['weakness_percentage']}%",
        f"Class Balance Ratio:       {report['class_balance_ratio']}",
        f"Duplicate Rows (Full):     {report['duplicate_rows']}",
        f"Duplicate Feature Vectors: {report['duplicate_feature_rows']}",
        f"Constant Features:         {', '.join(report['constant_features']) if report['constant_features'] else 'None'}",
        "------------------------------------------------------------",
        "TARGET LEAKAGE ANALYSIS:",
        f"Primary Leakage Risks:     {PRIMARY_LEAKAGE_FEATURES}",
        f"All Flagged Leakage Risks: {report['target_leakage_risks']}",
        "------------------------------------------------------------",
        "DATASET SUFFICIENCY FOR ML:",
        f"Sufficient for ML:         {report['dataset_sufficiency']['is_sufficient_for_ml']}",
        f"Assessment Detail:         {report['dataset_sufficiency']['reason']}",
        "============================================================",
    ]

    report_str = "\n".join(lines)
    return report_str
