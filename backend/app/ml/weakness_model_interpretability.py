"""
WEAKNESS ML MODEL INTERPRETABILITY ANALYSIS MODULE (STEP 4A)

Provides model interpretability and univariate feature diagnostics for the regularized
Logistic Regression behavioral classifier (StandardScaler + LogisticRegression(L2)).

ANALYSIS & INTERPRETABILITY ONLY:
- Does NOT integrate predictions into production APIs, scoring, database schemas, or assessment logic.
- Does NOT claim causal relationships (uses non-causal association language).
- Does NOT mutate input datasets or training data.
"""

import copy
import sys
import os
import math
from typing import List, Dict, Any, Union, Optional, Tuple
import numpy as np
import pandas as pd

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.ml.weakness_validation_audit import (
    load_dataset_from_db,
    generate_demonstration_audit_dataset
)
from app.ml.weakness_model import (
    run_weakness_experiment,
    EXPERIMENT_PURE_BEHAVIORAL_FEATURES,
    TARGET_LABEL_KEY
)


def extract_model_coefficients(
    model: Any,
    feature_names: List[str]
) -> List[Dict[str, Any]]:
    """
    Extracts standardized coefficients from a trained sklearn LogisticRegression pipeline or model.

    Parameters:
        model: Trained sklearn Pipeline or LogisticRegression model.
        feature_names: List of feature names corresponding to model input columns.

    Returns:
        List of dicts containing feature coefficient statistics:
            - feature: str
            - coefficient: float
            - absolute_coefficient: float
            - direction: str ("positive", "negative", "zero")
            - normalized_relative_importance: float
            - description: str (non-causal association statement)
    """
    if model is None:
        raise ValueError("Cannot extract coefficients from None or uninitialized model.")

    clf = None
    if hasattr(model, "named_steps") and "classifier" in model.named_steps:
        clf = model.named_steps["classifier"]
    elif hasattr(model, "coef_"):
        clf = model

    if clf is None or not hasattr(clf, "coef_"):
        raise ValueError("Provided model object does not contain fitted coefficients (coef_).")

    raw_coefs = clf.coef_[0] if clf.coef_.ndim == 2 else clf.coef_

    if len(raw_coefs) != len(feature_names):
        raise ValueError(
            f"Length mismatch: model coefficients length ({len(raw_coefs)}) "
            f"does not match feature_names length ({len(feature_names)})."
        )

    abs_coefs = [abs(float(c)) for c in raw_coefs]
    total_abs = sum(abs_coefs)

    records: List[Dict[str, Any]] = []
    for f_name, raw_c, abs_c in zip(feature_names, raw_coefs, abs_coefs):
        c_val = round(float(raw_c), 4)
        abs_val = round(float(abs_c), 4)

        if c_val > 0:
            direction = "positive"
            desc = "associated with higher model-predicted weakness probability"
        elif c_val < 0:
            direction = "negative"
            desc = "associated with lower model-predicted weakness probability"
        else:
            direction = "zero"
            desc = "associated with neutral/no change in model-predicted weakness probability"

        rel_imp = round(float(abs_c / total_abs), 4) if total_abs > 0 else 0.0

        records.append({
            "feature": f_name,
            "coefficient": c_val,
            "absolute_coefficient": abs_val,
            "direction": direction,
            "normalized_relative_importance": rel_imp,
            "description": f"Higher values of '{f_name}' are {desc}."
        })

    return records


def rank_feature_importance(
    coef_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Ranks features by absolute standardized coefficient magnitude.

    Parameters:
        coef_records: List of feature coefficient dicts from extract_model_coefficients.

    Returns:
        Dict containing ranked feature analysis:
            - ranked_features: List of feature dicts sorted descending by absolute_coefficient
            - top_3_features: List of top 3 feature names
            - top_5_features: List of top 5 feature names
            - weakest_features: List of bottom 3 feature names
            - positive_direction_features: List of positive-direction feature names
            - negative_direction_features: List of negative-direction feature names
    """
    if not coef_records:
        return {
            "ranked_features": [],
            "top_3_features": [],
            "top_5_features": [],
            "weakest_features": [],
            "positive_direction_features": [],
            "negative_direction_features": []
        }

    # Sort descending by absolute coefficient, breaking ties deterministically by feature name
    sorted_records = sorted(
        coef_records,
        key=lambda r: (-r["absolute_coefficient"], r["feature"])
    )

    all_names = [r["feature"] for r in sorted_records]
    top_3 = all_names[:3]
    top_5 = all_names[:5]

    # Weakest features (bottom 3) sorted from smallest to largest magnitude
    weakest_sorted = sorted(
        coef_records,
        key=lambda r: (r["absolute_coefficient"], r["feature"])
    )
    weakest_3 = [r["feature"] for r in weakest_sorted[:3]]

    pos_features = [r["feature"] for r in coef_records if r["direction"] == "positive"]
    neg_features = [r["feature"] for r in coef_records if r["direction"] == "negative"]

    return {
        "ranked_features": sorted_records,
        "top_3_features": top_3,
        "top_5_features": top_5,
        "weakest_features": weakest_3,
        "positive_direction_features": pos_features,
        "negative_direction_features": neg_features
    }


def perform_feature_sanity_checks(
    dataset: List[Dict[str, Any]],
    feature_names: List[str]
) -> Dict[str, Any]:
    """
    Performs behavioral feature quality checks (missing values, zero variance, ranges, outliers, group parity).

    Parameters:
        dataset: List of dataset records.
        feature_names: List of feature names to inspect.

    Returns:
        Dict containing quality checks per feature and overall flags.
    """
    if not dataset or not feature_names:
        return {}

    total_rows = len(dataset)
    g0_rows = [r for r in dataset if r.get(TARGET_LABEL_KEY, 0) == 0]
    g1_rows = [r for r in dataset if r.get(TARGET_LABEL_KEY, 0) == 1]

    results: Dict[str, Any] = {}

    for f in feature_names:
        vals = []
        for r in dataset:
            v = r.get(f)
            if v is not None:
                try:
                    f_v = float(v)
                    if not math.isnan(f_v):
                        vals.append(f_v)
                except (ValueError, TypeError):
                    pass

        missing_count = total_rows - len(vals)
        missing_pct = round((missing_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0

        if not vals:
            results[f] = {
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "zero_variance": True,
                "min": None,
                "max": None,
                "mean": None,
                "std": None,
                "outliers_count": 0,
                "identical_groups": True,
                "status": "MISSING_DATA"
            }
            continue

        arr = np.array(vals, dtype=float)
        f_min = round(float(np.min(arr)), 4)
        f_max = round(float(np.max(arr)), 4)
        f_mean = round(float(np.mean(arr)), 4)
        f_std = round(float(np.std(arr)), 4)
        zero_var = (f_std == 0.0) or (f_min == f_max)

        # Extreme outliers using IQR rule (outside Q1 - 3*IQR or Q3 + 3*IQR)
        q25, q75 = np.percentile(arr, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - 3.0 * iqr
        upper_bound = q75 + 3.0 * iqr
        outliers_count = int(np.sum((arr < lower_bound) | (arr > upper_bound)))

        # Group comparison for identical values between weakness (1) and non-weakness (0)
        g0_vals = [float(r[f]) for r in g0_rows if f in r and r[f] is not None]
        g1_vals = [float(r[f]) for r in g1_rows if f in r and r[f] is not None]

        identical_groups = False
        if g0_vals and g1_vals:
            g0_mean, g1_mean = np.mean(g0_vals), np.mean(g1_vals)
            g0_std, g1_std = np.std(g0_vals), np.std(g1_vals)
            if abs(g0_mean - g1_mean) < 1e-6 and abs(g0_std - g1_std) < 1e-6:
                identical_groups = True

        results[f] = {
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "zero_variance": zero_var,
            "min": f_min,
            "max": f_max,
            "mean": f_mean,
            "std": f_std,
            "outliers_count": outliers_count,
            "identical_groups": identical_groups,
            "status": "SUSPICIOUS" if (zero_var or identical_groups or missing_count > 0) else "OK"
        }

    return results


def compute_univariate_stats(
    dataset: List[Dict[str, Any]],
    feature_names: List[str],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Any]:
    """
    Computes simple descriptive statistics separately for is_weakness = 0 and is_weakness = 1.

    Parameters:
        dataset: List of dataset records.
        feature_names: List of feature names to summarize.
        target_key: Key for binary target label.

    Returns:
        Dict mapping feature name to statistics for group 0 and group 1.
    """
    if not dataset or not feature_names:
        return {}

    g0_records = [r for r in dataset if target_key in r and int(r[target_key]) == 0]
    g1_records = [r for r in dataset if target_key in r and int(r[target_key]) == 1]

    stats: Dict[str, Any] = {}

    def get_group_stats(records: List[Dict[str, Any]], feature: str) -> Dict[str, Any]:
        vals = []
        for r in records:
            if feature in r and r[feature] is not None:
                try:
                    fv = float(r[feature])
                    if not math.isnan(fv):
                        vals.append(fv)
                except (ValueError, TypeError):
                    pass

        if not vals:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0
            }

        arr = np.array(vals, dtype=float)
        return {
            "count": len(vals),
            "mean": round(float(np.mean(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4)
        }

    for f in feature_names:
        stats[f] = {
            "is_weakness_0": get_group_stats(g0_records, f),
            "is_weakness_1": get_group_stats(g1_records, f)
        }

    return stats


def compute_effect_sizes(
    dataset: List[Dict[str, Any]],
    feature_names: List[str],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Dict[str, Any]]:
    """
    Computes Standardized Mean Difference (Cohen's d) for each feature between group 1 and group 0.

    d = (mean_1 - mean_0) / s_pooled

    Parameters:
        dataset: List of dataset records.
        feature_names: List of feature names.
        target_key: Binary target key.

    Returns:
        Dict mapping feature name to Cohen's d effect size statistics.
    """
    if not dataset or not feature_names:
        return {}

    g0_records = [r for r in dataset if target_key in r and int(r[target_key]) == 0]
    g1_records = [r for r in dataset if target_key in r and int(r[target_key]) == 1]

    results: Dict[str, Dict[str, Any]] = {}

    for f in feature_names:
        g0_vals = [float(r[f]) for r in g0_records if f in r and r[f] is not None]
        g1_vals = [float(r[f]) for r in g1_records if f in r and r[f] is not None]

        n0, n1 = len(g0_vals), len(g1_vals)

        if n0 < 2 or n1 < 2:
            results[f] = {
                "cohens_d": 0.0,
                "effect_magnitude": "negligible",
                "note": "Insufficient samples in one or both target groups."
            }
            continue

        m0, m1 = np.mean(g0_vals), np.mean(g1_vals)
        s0, s1 = np.std(g0_vals, ddof=1), np.std(g1_vals, ddof=1)

        # Pooled standard deviation
        numerator = (n0 - 1) * (s0 ** 2) + (n1 - 1) * (s1 ** 2)
        denominator = n0 + n1 - 2

        if denominator > 0 and numerator > 0:
            s_pooled = math.sqrt(numerator / denominator)
        else:
            s_pooled = 0.0

        if s_pooled > 1e-9:
            d = round(float((m1 - m0) / s_pooled), 4)
        else:
            d = 0.0

        abs_d = abs(d)
        if abs_d >= 0.8:
            mag = "large"
        elif abs_d >= 0.5:
            mag = "medium"
        elif abs_d >= 0.2:
            mag = "small"
        else:
            mag = "negligible"

        results[f] = {
            "cohens_d": d,
            "absolute_cohens_d": abs_d,
            "mean_diff": round(float(m1 - m0), 4),
            "effect_magnitude": mag
        }

    return results


def investigate_roc_auc_drivers(
    ranked_info: Dict[str, Any],
    univariate_stats: Dict[str, Any],
    effect_sizes: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determines whether the extremely high ROC-AUC (~99.39%) is driven by:
    A. several behavioral features providing complementary signal
    OR
    B. one or two suspicious features dominating the model
    OR
    C. an unexpected data/feature construction artifact.

    Returns structured diagnostic findings.
    """
    ranked_feats = ranked_info.get("ranked_features", [])

    if not ranked_feats:
        return {
            "primary_driver_category": "UNKNOWN",
            "explanation": "No ranked feature information available.",
            "dominating_features": [],
            "artifact_details": []
        }

    top_feat_name = ranked_feats[0]["feature"]
    top_feat_imp = ranked_feats[0]["normalized_relative_importance"]

    # Check top 2 features relative importance
    top_2_imp = sum(r["normalized_relative_importance"] for r in ranked_feats[:2])

    dominating_feats = [r["feature"] for r in ranked_feats if r["normalized_relative_importance"] >= 0.35]

    # Check for volume/count construction artifacts (timed_questions_count, questions_answered_count)
    volume_artifacts = [f for f in ["timed_questions_count", "questions_answered_count"] if f in [r["feature"] for r in ranked_feats[:2]]]

    if volume_artifacts and top_2_imp > 0.70:
        cat = "B_AND_C_FEATURE_CONSTRUCTION_ARTIFACT"
        expl = (
            f"The high ROC-AUC (~99.39%) is strongly DOMINATED by feature construction artifacts: "
            f"the two question volume features ({', '.join(volume_artifacts)}) account for "
            f"{round(top_2_imp * 100, 1)}% of total model importance. "
            f"In the assessment dataset, unassessed or incomplete skills record 0 answered questions, "
            f"which deterministically produces total_score = 0.0 (< 0.60 threshold) and is_weakness = 1. "
            f"Therefore, question volume counts act as near-perfect structural proxies for the target rule."
        )
    elif top_2_imp > 0.60:
        cat = "B_DOMINATING_SUSPICIOUS_FEATURES"
        expl = (
            f"The high ROC-AUC is primarily driven by one or two dominating features "
            f"({', '.join(dominating_feats)}) which account for {round(top_2_imp * 100, 1)}% of model weight."
        )
    else:
        cat = "A_COMPLEMENTARY_BEHAVIORAL_SIGNAL"
        expl = (
            "The high ROC-AUC appears to be distributed across multiple behavioral features "
            "providing complementary predictive signal."
        )

    return {
        "primary_driver_category": cat,
        "explanation": expl,
        "dominating_features": dominating_feats,
        "volume_artifacts": volume_artifacts,
        "top_2_normalized_importance_sum": top_2_imp
    }


def run_interpretability_analysis(
    dataset: Optional[List[Dict[str, Any]]] = None,
    experiment_type: str = "PURE_BEHAVIORAL"
) -> Dict[str, Any]:
    """
    Executes the complete Step 4A Weakness ML Model Interpretability Analysis.

    Parameters:
        dataset: Optional custom dataset. If None, loads from DB or falls back to demonstration dataset.
        experiment_type: Feature set to analyze (default 'PURE_BEHAVIORAL').

    Returns:
        Dict containing structured analysis report including coefficients, rankings, univariate stats,
        effect sizes, sanity checks, ROC-AUC driver analysis, and formatted text report.
    """
    if dataset is None or len(dataset) == 0:
        dataset = load_dataset_from_db()
        if not dataset or len(dataset) < 50:
            dataset = generate_demonstration_audit_dataset(num_candidates=42, random_seed=42)

    # 1. Run pure behavioral experiment to fit standard model
    exp_result = run_weakness_experiment(dataset, experiment_type=experiment_type, use_group_cv=True)
    model = exp_result["model"]
    feature_names = exp_result["feature_names"]

    # 2. Extract coefficients
    coef_records = extract_model_coefficients(model, feature_names)

    # 3. Rank feature importance
    ranked_info = rank_feature_importance(coef_records)

    # 4. Behavioral feature sanity checks
    sanity_checks = perform_feature_sanity_checks(dataset, feature_names)

    # 5. Univariate analysis
    univariate_stats = compute_univariate_stats(dataset, feature_names)

    # 6. Effect sizes
    effect_sizes = compute_effect_sizes(dataset, feature_names)

    # 7. Investigate ROC-AUC driver
    driver_analysis = investigate_roc_auc_drivers(ranked_info, univariate_stats, effect_sizes)

    report_dict = {
        "sample_count": len(dataset),
        "experiment_name": exp_result["experiment_name"],
        "metrics": exp_result["metrics"],
        "coefficients": coef_records,
        "ranking": ranked_info,
        "sanity_checks": sanity_checks,
        "univariate_stats": univariate_stats,
        "effect_sizes": effect_sizes,
        "roc_auc_driver_analysis": driver_analysis,
        "target_limitation_notice": (
            "IMPORTANT INTERPRETATION LIMITATION: The target is generated from baseline assessment rules "
            "(level_gap > 0 OR total_score < 0.60). Therefore, feature importance shows which behavioral "
            "features are associated with the model's prediction of this assessment-derived target. "
            "It does NOT prove these features independently measure real-world skill weakness."
        )
    }

    report_text = format_interpretability_report(report_dict)
    report_dict["report_text"] = report_text

    return report_dict


def format_interpretability_report(report_dict: Dict[str, Any]) -> str:
    """
    Formats the interpretability analysis output into a human-readable text report.
    """
    ranking = report_dict.get("ranking", {})
    ranked_feats = ranking.get("ranked_features", [])
    sanity = report_dict.get("sanity_checks", {})
    uni = report_dict.get("univariate_stats", {})
    eff = report_dict.get("effect_sizes", {})
    driver = report_dict.get("roc_auc_driver_analysis", {})
    metrics = report_dict.get("metrics", {})

    lines = [
        "============================================================",
        "     STEP 4A: WEAKNESS ML MODEL INTERPRETABILITY REPORT     ",
        "============================================================",
        f"Experiment: {report_dict.get('experiment_name')} (Sample Count: {report_dict.get('sample_count')})",
        f"Model Performance (CV): Accuracy={metrics.get('accuracy')} | F1={metrics.get('f1')} | ROC-AUC={metrics.get('roc_auc')} | PR-AUC={metrics.get('pr_auc')}",
        "------------------------------------------------------------",
        "1. RANKED STANDARDIZED FEATURE COEFFICIENTS:",
    ]

    for idx, r in enumerate(ranked_feats, 1):
        lines.append(
            f"   {idx}. {r['feature']:34s} | Coef: {r['coefficient']:+7.4f} | Abs: {r['absolute_coefficient']:6.4f} | "
            f"RelImp: {r['normalized_relative_importance']*100:5.1f}% | Dir: {r['direction']}"
        )

    lines.extend([
        "------------------------------------------------------------",
        "2. FEATURE SUMMARY GROUPS:",
        f"   - Top 3 Features:    {', '.join(ranking.get('top_3_features', []))}",
        f"   - Top 5 Features:    {', '.join(ranking.get('top_5_features', []))}",
        f"   - Weakest Features:  {', '.join(ranking.get('weakest_features', []))}",
        f"   - Positive Direction: {', '.join(ranking.get('positive_direction_features', []))}",
        f"   - Negative Direction: {', '.join(ranking.get('negative_direction_features', []))}",
        "------------------------------------------------------------",
        "3. UNIVARIATE STATISTICS & EFFECT SIZES (Group 0: non-weakness vs Group 1: weakness):",
    ])

    for f_name, f_uni in uni.items():
        g0 = f_uni.get("is_weakness_0", {})
        g1 = f_uni.get("is_weakness_1", {})
        e_stat = eff.get(f_name, {})

        lines.append(f"   Feature: {f_name}")
        lines.append(
            f"     is_weakness=0 (n={g0.get('count')}): mean={g0.get('mean'):.4f}, median={g0.get('median'):.4f}, std={g0.get('std'):.4f}, range=[{g0.get('min')}, {g0.get('max')}]"
        )
        lines.append(
            f"     is_weakness=1 (n={g1.get('count')}): mean={g1.get('mean'):.4f}, median={g1.get('median'):.4f}, std={g1.get('std'):.4f}, range=[{g1.get('min')}, {g1.get('max')}]"
        )
        lines.append(
            f"     Effect Size (Cohen's d): {e_stat.get('cohens_d', 0.0):+.4f} ({e_stat.get('effect_magnitude', 'unknown')})"
        )

    lines.extend([
        "------------------------------------------------------------",
        "4. BEHAVIORAL FEATURE QUALITY & SANITY CHECKS:",
    ])

    for f_name, s_info in sanity.items():
        lines.append(
            f"   - {f_name:34s} | Missing: {s_info.get('missing_count')} | Const: {s_info.get('zero_variance')} | Outliers: {s_info.get('outliers_count')} | Status: {s_info.get('status')}"
        )

    lines.extend([
        "------------------------------------------------------------",
        "5. MOST IMPORTANT INVESTIGATION: ROC-AUC DRIVER ANALYSIS:",
        f"   Primary Category: {driver.get('primary_driver_category')}",
        f"   Detailed Explanation: {driver.get('explanation')}",
        "------------------------------------------------------------",
        "6. METHODOLOGICAL & INTERPRETATION LIMITATIONS:",
        report_dict.get("target_limitation_notice", ""),
        "============================================================",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    rep = run_interpretability_analysis()
    print(rep["report_text"])
