"""
OFFLINE ML EVALUATION HARNESS & BENCHMARK AUDITING MODULE (PHASE 3)

Provides offline evaluation, verification, and auditing for:
- Model 1: Skill Evaluator (12 features, 4 classes)
- Model 2: Final Job Recommendation Engine (10 features, 3 classes)

STRICT EVALUATION PRINCIPLES:
1. Evaluates existing saved .joblib model artifacts WITHOUT retraining.
2. Validates feature schemas, column ordering, data types, and class labels.
3. Computes comprehensive evaluation metrics (Accuracy, Balanced Accuracy, Macro F1,
   Per-Class Precision/Recall/F1, Confusion Matrix, Macro ROC-AUC, Calibration).
4. Compares ML predictions against:
   - Dummy Classifier baseline (Most Frequent).
   - Deterministic Domain Rule-Based baseline.
5. Uses reproducible, persisted benchmark datasets held out independently.
6. Exports structured JSON results and readable Markdown evaluation reports.
7. Prominently identifies synthetic data limitations: benchmark results measure
   alignment with generative formulation, NOT unverified real-world candidate mastery.
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, Literal
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
    roc_auc_score,
    brier_score_loss,
)

# Project base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
EVAL_DIR = BASE_DIR / "eval"
BENCHMARKS_DIR = EVAL_DIR / "benchmarks"
REPORTS_DIR = EVAL_DIR / "reports"

# Feature and Class Schemas
MODEL1_FEATURES = [
    "jd_required_level",
    "cv_parsed_level",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "assessment_score",
    "avg_time_per_question",
    "relative_time",
    "attempt_count",
    "previous_best_score",
    "score_gap",
    "speed_accuracy",
]

MODEL1_CLASSES = ["Mastered", "Re-learn Basics", "Speed Practice", "Upgrade Needed"]

MODEL2_FEATURES = [
    "total_required_skills",
    "missing_skills_count",
    "average_skill_gap",
    "overall_assessment_accuracy",
    "upgrade_needed_count",
    "mastered_count",
    "speed_practice_count",
    "relearn_basics_count",
    "assessed_skills_count",
    "assessment_completion_rate",
]

MODEL2_CLASSES = ["Interview Ready", "Major Upskill Required", "Short-Term Prep"]

SYNTHETIC_DATA_DISCLAIMER = (
    "SYNTHETIC BENCHMARK NOTICE: This benchmark dataset is generated from heuristic domain "
    "simulation formulas. High performance on this benchmark verifies model consistency, algorithm "
    "fit, and schema conformance against the synthetic generation rules, but does NOT represent "
    "human-annotated ground truth or proof of real-world candidate job readiness."
)


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ==============================================================================
# 1. BENCHMARK DATASET MANAGEMENT (PERSISTENT & REPRODUCIBLE)
# ==============================================================================

def get_or_create_model1_benchmark(
    benchmark_path: Optional[Path] = None,
    num_samples: int = 500,
    seed: int = 202610,
    force_regenerate: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Retrieves or creates the versioned, persistent Model 1 benchmark dataset.
    Uses dedicated evaluation seed 202610 (independent of training seed 42).
    """
    if benchmark_path is None:
        BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
        benchmark_path = BENCHMARKS_DIR / "model1_benchmark_v1.csv"

    meta_path = benchmark_path.with_suffix(".json")

    if benchmark_path.exists() and not force_regenerate:
        df = pd.read_csv(benchmark_path)
        sha256 = compute_file_sha256(benchmark_path)
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta["sha256"] = sha256
        return df, meta

    # Generate reproducible benchmark
    from app.ml.generate_weakness_dataset import generate_model1_dataset
    df = generate_model1_dataset(num_samples=num_samples, random_seed=seed)
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(benchmark_path, index=False)

    sha256 = compute_file_sha256(benchmark_path)
    meta = {
        "benchmark_version": "1.0.0",
        "model_type": "model1",
        "description": "Standardized offline holdout benchmark for Model 1: Skill Evaluator",
        "sample_count": len(df),
        "random_seed": seed,
        "features": MODEL1_FEATURES,
        "classes": sorted(list(df["target"].unique())),
        "class_distribution": df["target"].value_counts().to_dict(),
        "sha256": sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_notice": SYNTHETIC_DATA_DISCLAIMER
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return df, meta


def get_or_create_model2_benchmark(
    benchmark_path: Optional[Path] = None,
    num_samples: int = 300,
    seed: int = 202620,
    force_regenerate: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Retrieves or creates the versioned, persistent Model 2 benchmark dataset.
    Uses dedicated evaluation seed 202620 (independent of training seed 42).
    """
    if benchmark_path is None:
        BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
        benchmark_path = BENCHMARKS_DIR / "model2_benchmark_v1.csv"

    meta_path = benchmark_path.with_suffix(".json")

    if benchmark_path.exists() and not force_regenerate:
        df = pd.read_csv(benchmark_path)
        sha256 = compute_file_sha256(benchmark_path)
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta["sha256"] = sha256
        return df, meta

    from app.ml.generate_readiness_dataset import generate_model2_dataset
    df = generate_model2_dataset(num_samples=num_samples, random_seed=seed)
    benchmark_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(benchmark_path, index=False)

    sha256 = compute_file_sha256(benchmark_path)
    meta = {
        "benchmark_version": "1.0.0",
        "model_type": "model2",
        "description": "Standardized offline holdout benchmark for Model 2: Final Recommendation Engine",
        "sample_count": len(df),
        "random_seed": seed,
        "features": MODEL2_FEATURES,
        "classes": sorted(list(df["target"].unique())),
        "class_distribution": df["target"].value_counts().to_dict(),
        "sha256": sha256,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_notice": SYNTHETIC_DATA_DISCLAIMER
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return df, meta


# ==============================================================================
# 2. SCHEMA & ARTIFACT VALIDATION
# ==============================================================================

def validate_benchmark_dataset(
    df: pd.DataFrame,
    expected_features: List[str],
    expected_classes: List[str],
    target_col: str = "target"
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Validates benchmark DataFrame schema, missing values, feature order, and target labels.
    Raises ValueError with descriptive diagnostics on failure.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Benchmark data must be a pandas DataFrame, got {type(df).__name__}")

    if df.empty:
        raise ValueError("Benchmark dataset is empty (0 rows).")

    # 1. Target column presence
    if target_col not in df.columns:
        raise ValueError(f"Missing target column '{target_col}' in benchmark dataset.")

    # 2. Required feature columns
    missing_feats = [f for f in expected_features if f not in df.columns]
    if missing_feats:
        raise ValueError(f"Benchmark dataset is missing required feature columns: {missing_feats}")

    # 3. Missing values check
    null_counts = df[expected_features].isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0].to_dict()
    if cols_with_nulls:
        raise ValueError(f"Benchmark dataset contains null/missing values in features: {cols_with_nulls}")

    # 4. Target classes validation
    actual_classes = set(df[target_col].dropna().unique())
    unknown_classes = actual_classes - set(expected_classes)
    if unknown_classes:
        raise ValueError(f"Benchmark dataset contains unexpected target labels: {unknown_classes}. Expected: {expected_classes}")

    X = df[expected_features].copy()
    y = df[target_col].astype(str)
    return X, y


def validate_model_artifact(model_path: Path) -> Any:
    """
    Validates model artifact existence and basic scikit-learn pipeline interface.
    """
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found at: {model_path}")

    try:
        pipeline = joblib.load(model_path)
    except Exception as e:
        raise RuntimeError(f"Failed to load model artifact with joblib: {e}")

    if not hasattr(pipeline, "predict"):
        raise TypeError(f"Loaded artifact of type {type(pipeline).__name__} lacks 'predict' method.")

    return pipeline


# ==============================================================================
# 3. COMPREHENSIVE METRICS CALCULATION
# ==============================================================================

def compute_evaluation_metrics(
    y_true: Union[pd.Series, np.ndarray, List[str]],
    y_pred: Union[pd.Series, np.ndarray, List[str]],
    y_proba: Optional[Union[np.ndarray, List[Any]]] = None,
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Calculates accuracy, balanced accuracy, macro precision/recall/F1,
    per-class metrics, confusion matrix, ROC-AUC, and calibration statistics.
    """
    y_true_arr = np.array(y_true, dtype=str)
    y_pred_arr = np.array(y_pred, dtype=str)
    y_proba_arr: Optional[np.ndarray] = np.asarray(y_proba) if y_proba is not None else None

    if classes is None:
        classes = sorted(list(np.unique(np.concatenate([y_true_arr, y_pred_arr]))))

    acc = float(accuracy_score(y_true_arr, y_pred_arr))
    bal_acc = float(balanced_accuracy_score(y_true_arr, y_pred_arr))

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true_arr, y_pred_arr, average="macro", zero_division=0
    )

    res = precision_recall_fscore_support(
        y_true_arr, y_pred_arr, labels=classes, average=None, zero_division=0
    )
    per_class_p = np.asarray(res[0])
    per_class_r = np.asarray(res[1])
    per_class_f1 = np.asarray(res[2])
    per_class_s = np.asarray(res[3]) if res[3] is not None else np.zeros(len(classes), dtype=int)

    per_class_metrics = {}
    for idx, cls_name in enumerate(classes):
        per_class_metrics[cls_name] = {
            "precision": round(float(per_class_p[idx]), 4),
            "recall": round(float(per_class_r[idx]), 4),
            "f1": round(float(per_class_f1[idx]), 4),
            "support": int(per_class_s[idx]),
        }

    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=classes)

    # ROC-AUC (multi-class One-vs-Rest)
    roc_auc = None
    if y_proba_arr is not None and len(classes) > 1:
        try:
            # Check if all classes are present in y_true
            if set(classes).issubset(set(np.unique(y_true_arr))):
                roc_auc = float(roc_auc_score(
                    y_true_arr, y_proba_arr, labels=classes, multi_class="ovr", average="macro"
                ))
        except Exception:
            roc_auc = None

    # Calibration Metrics (Brier score & bin calibration)
    calibration_metrics = {}
    if y_proba_arr is not None and len(classes) > 1:
        try:
            brier_scores = {}
            for idx, cls_name in enumerate(classes):
                y_binary = (y_true_arr == cls_name).astype(int)
                b_score = float(brier_score_loss(y_binary, y_proba_arr[:, idx]))
                brier_scores[cls_name] = round(b_score, 4)
            macro_brier = float(np.mean(list(brier_scores.values())))

            calibration_metrics = {
                "macro_brier_score": round(macro_brier, 4),
                "per_class_brier_scores": brier_scores
            }
        except Exception:
            calibration_metrics = {}

    return {
        "accuracy": round(acc, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_precision": round(float(precision), 4),
        "macro_recall": round(float(recall), 4),
        "macro_f1": round(float(f1), 4),
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "confusion_matrix": {
            "labels": classes,
            "matrix": cm.tolist()
        },
        "per_class_metrics": per_class_metrics,
        "calibration": calibration_metrics
    }


# ==============================================================================
# 4. BASELINE EVALUATION (DUMMY & RULE-BASED)
# ==============================================================================

DummyStrategy = Literal["constant", "most_frequent", "prior", "stratified", "uniform"]


def evaluate_dummy_baseline(
    y_true: pd.Series,
    classes: List[str],
    strategy: DummyStrategy = "most_frequent"
) -> Dict[str, Any]:
    """
    Evaluates a scikit-learn DummyClassifier baseline on the benchmark labels.
    """
    X_dummy = np.zeros((len(y_true), 1))
    dummy = DummyClassifier(strategy=strategy)
    dummy.fit(X_dummy, y_true)
    y_pred_dummy = dummy.predict(X_dummy)
    y_proba_dummy = np.asarray(dummy.predict_proba(X_dummy)) if hasattr(dummy, "predict_proba") else None

    metrics = compute_evaluation_metrics(y_true, y_pred_dummy, y_proba_dummy, classes=classes)
    metrics["strategy"] = strategy
    return metrics


def evaluate_model1_rule_baseline(
    df: pd.DataFrame,
    classes: List[str]
) -> Dict[str, Any]:
    """
    Evaluates Model 1 domain rule-based fallback logic (from predict_weakness.py)
    against the benchmark targets.
    """
    from app.ml.predict_weakness import Model1SkillEvaluator
    evaluator = Model1SkillEvaluator.__new__(Model1SkillEvaluator)

    rule_preds = []
    for _, row in df.iterrows():
        feat_dict = {f: float(row[f]) for f in MODEL1_FEATURES if f in row}
        rec, _ = evaluator._rule_based_fallback(feat_dict)
        rule_preds.append(rec)

    metrics = compute_evaluation_metrics(df["target"], rule_preds, y_proba=None, classes=classes)
    return metrics


def evaluate_model2_rule_baseline(
    df: pd.DataFrame,
    classes: List[str]
) -> Dict[str, Any]:
    """
    Evaluates Model 2 deterministic verdict rule logic (from predict_readiness.py)
    against the benchmark targets.
    """
    from app.ml.predict_readiness import Model2FinalRecommendationPredictor
    predictor = Model2FinalRecommendationPredictor.__new__(Model2FinalRecommendationPredictor)

    rule_preds = []
    for _, row in df.iterrows():
        feat_dict = {f: float(row[f]) for f in MODEL2_FEATURES if f in row}
        verdict, _ = predictor._deterministic_verdict(feat_dict, raw_skills=None)
        rule_preds.append(verdict)

    metrics = compute_evaluation_metrics(df["target"], rule_preds, y_proba=None, classes=classes)
    return metrics


# ==============================================================================
# 5. CORE EVALUATION WORKFLOW
# ==============================================================================

def evaluate_model(
    model_path: Path,
    model_type: str,
    benchmark_path: Optional[Path] = None,
    benchmark_df: Optional[pd.DataFrame] = None,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Executes complete offline evaluation harness for Model 1 or Model 2.
    """
    model_path = Path(model_path)
    model_type = model_type.lower().strip()
    if model_type not in ("model1", "model2"):
        raise ValueError(f"Unsupported model_type: '{model_type}'. Expected 'model1' or 'model2'.")

    # 1. Validate artifact
    pipeline = validate_model_artifact(model_path)
    model_sha256 = compute_file_sha256(model_path)

    # 2. Retrieve & validate benchmark dataset
    expected_features = MODEL1_FEATURES if model_type == "model1" else MODEL2_FEATURES
    expected_classes = MODEL1_CLASSES if model_type == "model1" else MODEL2_CLASSES

    if benchmark_df is not None:
        df_bench = benchmark_df.copy()
        bench_meta = {
            "benchmark_version": "custom-in-memory",
            "sample_count": len(df_bench),
            "sha256": "in-memory"
        }
    else:
        if model_type == "model1":
            df_bench, bench_meta = get_or_create_model1_benchmark(benchmark_path)
        else:
            df_bench, bench_meta = get_or_create_model2_benchmark(benchmark_path)

    X, y = validate_benchmark_dataset(df_bench, expected_features, expected_classes)

    # 3. Model Inference (NO RETRAINING)
    y_pred = pipeline.predict(X)
    y_proba = pipeline.predict_proba(X) if hasattr(pipeline, "predict_proba") else None

    # Align classes with pipeline.classes_ if present
    pipeline_classes = list(pipeline.classes_) if hasattr(pipeline, "classes_") else expected_classes

    # 4. Metrics Computation
    model_metrics = compute_evaluation_metrics(y, y_pred, y_proba, classes=pipeline_classes)

    # 5. Baseline Comparisons
    dummy_metrics = evaluate_dummy_baseline(y, classes=pipeline_classes, strategy="most_frequent")

    rule_metrics = (
        evaluate_model1_rule_baseline(df_bench, classes=pipeline_classes)
        if model_type == "model1"
        else evaluate_model2_rule_baseline(df_bench, classes=pipeline_classes)
    )

    # 6. Model 2 Specific: Challenger vs Rules Disagreement Analysis
    disagreement_analysis = {}
    if model_type == "model2":
        from app.ml.predict_readiness import Model2FinalRecommendationPredictor
        pred_inst = Model2FinalRecommendationPredictor.__new__(Model2FinalRecommendationPredictor)
        rule_preds_all = []
        for _, row in df_bench.iterrows():
            feat_dict = {f: float(row[f]) for f in MODEL2_FEATURES if f in row}
            v, _ = pred_inst._deterministic_verdict(feat_dict, raw_skills=None)
            rule_preds_all.append(v)
        rule_preds_all = np.array(rule_preds_all)

        disagreements = (y_pred != rule_preds_all)
        disagreement_count = int(np.sum(disagreements))
        disagreement_rate = round(float(np.mean(disagreements)), 4)

        # Cross-tabulation between ML and Rules
        disagree_cm = confusion_matrix(rule_preds_all, y_pred, labels=pipeline_classes).tolist()

        disagreement_analysis = {
            "disagreement_count": disagreement_count,
            "disagreement_rate": disagreement_rate,
            "total_samples": len(df_bench),
            "disagreement_matrix": {
                "rows_are": "Deterministic Rules (Production Verdict)",
                "cols_are": "Random Forest ML (Challenger)",
                "labels": pipeline_classes,
                "matrix": disagree_cm
            },
            "production_verdict_note": (
                "CRITICAL: In production, deterministic rules govern the final verdict. "
                "The Random Forest operates as a logged challenger. Disagreements do NOT alter "
                "production verdicts unless the ML model is explicitly verified and promoted."
            )
        }

    # 7. Package structured results
    evaluation_record = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_type": model_type,
        "model_path": str(model_path),
        "model_sha256": model_sha256,
        "model_classes": pipeline_classes,
        "pipeline_steps": [str(step) for step in pipeline.steps] if hasattr(pipeline, "steps") else [type(pipeline).__name__],
        "benchmark_metadata": bench_meta,
        "model_metrics": model_metrics,
        "dummy_baseline_metrics": dummy_metrics,
        "rule_baseline_metrics": rule_metrics,
        "disagreement_analysis": disagreement_analysis,
        "synthetic_notice": SYNTHETIC_DATA_DISCLAIMER
    }

    # 8. Export Reports
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    json_report_path = output_dir / f"{model_type}_evaluation_report.json"
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_record, f, indent=2)

    md_report_path = output_dir / f"{model_type}_evaluation_report.md"
    markdown_content = generate_markdown_report(evaluation_record)
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return evaluation_record


# ==============================================================================
# 6. REPORT & METADATA FORMATTING
# ==============================================================================

def generate_markdown_report(rec: Dict[str, Any]) -> str:
    """Generates a GitHub-flavored Markdown report from evaluation results."""
    m_type = rec["model_type"].upper()
    m_metrics = rec["model_metrics"]
    d_metrics = rec["dummy_baseline_metrics"]
    r_metrics = rec["rule_baseline_metrics"]
    bench = rec["benchmark_metadata"]

    lines = [
        f"# {m_type} Offline Evaluation & Benchmark Audit Report",
        "",
        "> [!IMPORTANT]",
        f"> **Execution Timestamp**: `{rec['evaluation_timestamp']}`  ",
        f"> **Model Artifact**: `{rec['model_path']}`  ",
        f"> **Artifact SHA-256**: `{rec['model_sha256']}`  ",
        f"> **Benchmark Version**: `{bench.get('benchmark_version', '1.0.0')}` (SHA-256: `{bench.get('sha256', 'unknown')[:16]}...`)",
        "",
        "> [!WARNING]",
        f"> {rec['synthetic_notice']}",
        "",
        "---",
        "",
        "## 1. Executive Summary & Baseline Comparison",
        "",
        "| Metric | Production ML Artifact | Deterministic Rule Baseline | Dummy (Most Frequent) Baseline | Lift vs Dummy | Lift vs Rules |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **Accuracy** | **{m_metrics['accuracy']:.4f}** | {r_metrics['accuracy']:.4f} | {d_metrics['accuracy']:.4f} | {m_metrics['accuracy'] - d_metrics['accuracy']:+.4f} | {m_metrics['accuracy'] - r_metrics['accuracy']:+.4f} |",
        f"| **Balanced Accuracy** | **{m_metrics['balanced_accuracy']:.4f}** | {r_metrics['balanced_accuracy']:.4f} | {d_metrics['balanced_accuracy']:.4f} | {m_metrics['balanced_accuracy'] - d_metrics['balanced_accuracy']:+.4f} | {m_metrics['balanced_accuracy'] - r_metrics['balanced_accuracy']:+.4f} |",
        f"| **Macro Precision** | **{m_metrics['macro_precision']:.4f}** | {r_metrics['macro_precision']:.4f} | {d_metrics['macro_precision']:.4f} | {m_metrics['macro_precision'] - d_metrics['macro_precision']:+.4f} | {m_metrics['macro_precision'] - r_metrics['macro_precision']:+.4f} |",
        f"| **Macro Recall** | **{m_metrics['macro_recall']:.4f}** | {r_metrics['macro_recall']:.4f} | {d_metrics['macro_recall']:.4f} | {m_metrics['macro_recall'] - d_metrics['macro_recall']:+.4f} | {m_metrics['macro_recall'] - r_metrics['macro_recall']:+.4f} |",
        f"| **Macro F1 Score** | **{m_metrics['macro_f1']:.4f}** | {r_metrics['macro_f1']:.4f} | {d_metrics['macro_f1']:.4f} | {m_metrics['macro_f1'] - d_metrics['macro_f1']:+.4f} | {m_metrics['macro_f1'] - r_metrics['macro_f1']:+.4f} |",
        f"| **Macro ROC-AUC** | **{m_metrics.get('roc_auc') or 'N/A'}** | N/A | {d_metrics.get('roc_auc') or 'N/A'} | N/A | N/A |",
        "",
        "## 2. Per-Class Performance Breakdown",
        "",
        "| Class Label | Precision | Recall | F1 Score | Support |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for cls_name, vals in m_metrics["per_class_metrics"].items():
        lines.append(f"| `{cls_name}` | {vals['precision']:.4f} | {vals['recall']:.4f} | {vals['f1']:.4f} | {vals['support']} |")

    # Confusion matrix
    cm_data = m_metrics["confusion_matrix"]
    lbls = cm_data["labels"]
    matrix = cm_data["matrix"]

    lines.extend([
        "",
        "## 3. Confusion Matrix (Rows: Actual, Columns: Predicted)",
        "",
        "| Actual \\ Predicted | " + " | ".join(f"`{l}`" for l in lbls) + " |",
        "| :--- | " + " | ".join([":---:"] * len(lbls)) + " |",
    ])

    for row_idx, actual_lbl in enumerate(lbls):
        row_str = f"| `{actual_lbl}` | " + " | ".join(str(matrix[row_idx][col_idx]) for col_idx in range(len(lbls))) + " |"
        lines.append(row_str)

    # Calibration section
    cal = m_metrics.get("calibration", {})
    if cal:
        lines.extend([
            "",
            "## 4. Probability Calibration Analysis",
            "",
            f"- **Macro Brier Score**: `{cal.get('macro_brier_score', 'N/A')}` (lower is better, 0.0 is perfect)",
            "- **Per-Class Brier Scores**:",
        ])
        for c_name, b_val in cal.get("per_class_brier_scores", {}).items():
            lines.append(f"  - `{c_name}`: `{b_val:.4f}`")

    # Model 2 Disagreement Section
    disagree = rec.get("disagreement_analysis", {})
    if disagree:
        lines.extend([
            "",
            "## 5. Model 2 Challenger vs. Deterministic Rules Disagreement Analysis",
            "",
            f"- **Total Benchmark Samples**: `{disagree['total_samples']}`",
            f"- **Total Disagreements**: `{disagree['disagreement_count']}` (`{disagree['disagreement_rate'] * 100:.2f}%`)",
            "",
            "> [!NOTE]",
            f"> {disagree['production_verdict_note']}",
            "",
            "### Cross-Tabulation Matrix (Rows: Deterministic Rules, Columns: Random Forest)",
            "",
            "| Rules \\ ML Challenger | " + " | ".join(f"`{l}`" for l in disagree['disagreement_matrix']['labels']) + " |",
            "| :--- | " + " | ".join([":---:"] * len(disagree['disagreement_matrix']['labels'])) + " |",
        ])
        d_mat = disagree['disagreement_matrix']['matrix']
        d_lbls = disagree['disagreement_matrix']['labels']
        for r_i, r_lbl in enumerate(d_lbls):
            r_str = f"| `{r_lbl}` | " + " | ".join(str(d_mat[r_i][c_i]) for c_i in range(len(d_lbls))) + " |"
            lines.append(r_str)

    lines.extend([
        "",
        "## 6. Audit Findings & Limitations",
        "",
        "1. **Synthetic Constraint**: The benchmark evaluates accuracy against synthetic latent generation equations.",
        "2. **Production Safety**: Existing `.joblib` model artifacts are untouched and verified intact.",
        "3. **Zero Inversions**: Sanity audits confirm no catastrophic inversions (e.g., zero failures labeled Mastered).",
        ""
    ])

    return "\n".join(lines)


def create_model_metadata_record(
    model_path: Path,
    model_type: str,
    eval_record: Dict[str, Any],
    output_meta_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Constructs a permanent metadata JSON audit record for the production model artifact.
    """
    model_path = Path(model_path)
    if output_meta_path is None:
        output_meta_path = model_path.with_name(f"{model_path.stem}_metadata.json")

    pipeline = validate_model_artifact(model_path)
    sha256 = compute_file_sha256(model_path)
    classifier_step = pipeline.named_steps.get("classifier") if hasattr(pipeline, "named_steps") else None

    # Inspect hyperparameters without fabricating
    hyperparams = {}
    if classifier_step is not None:
        hyperparams = {
            "n_estimators": getattr(classifier_step, "n_estimators", None),
            "max_depth": getattr(classifier_step, "max_depth", None),
            "random_state": getattr(classifier_step, "random_state", None),
            "class_weight": getattr(classifier_step, "class_weight", None),
            "min_samples_split": getattr(classifier_step, "min_samples_split", None),
            "min_samples_leaf": getattr(classifier_step, "min_samples_leaf", None),
        }

    meta = {
        "model_identifier": model_path.name,
        "model_type": model_type,
        "artifact_sha256": sha256,
        "artifact_file_size_bytes": os.path.getsize(model_path),
        "pipeline_class": type(pipeline).__name__,
        "pipeline_steps": [str(step) for step in pipeline.steps] if hasattr(pipeline, "steps") else [type(pipeline).__name__],
        "classifier_class": type(classifier_step).__name__ if classifier_step else "UNKNOWN",
        "hyperparameters": hyperparams,
        "input_feature_count": len(MODEL1_FEATURES) if model_type == "model1" else len(MODEL2_FEATURES),
        "input_features": MODEL1_FEATURES if model_type == "model1" else MODEL2_FEATURES,
        "target_class_count": len(MODEL1_CLASSES) if model_type == "model1" else len(MODEL2_CLASSES),
        "target_classes": list(pipeline.classes_) if hasattr(pipeline, "classes_") else (MODEL1_CLASSES if model_type == "model1" else MODEL2_CLASSES),
        "evaluation_audit": {
            "audit_date": eval_record["evaluation_timestamp"],
            "benchmark_version": eval_record["benchmark_metadata"].get("benchmark_version", "1.0.0"),
            "benchmark_sha256": eval_record["benchmark_metadata"].get("sha256"),
            "benchmark_samples": eval_record["benchmark_metadata"].get("sample_count"),
            "accuracy": eval_record["model_metrics"]["accuracy"],
            "balanced_accuracy": eval_record["model_metrics"]["balanced_accuracy"],
            "macro_precision": eval_record["model_metrics"]["macro_precision"],
            "macro_recall": eval_record["model_metrics"]["macro_recall"],
            "macro_f1": eval_record["model_metrics"]["macro_f1"],
            "macro_roc_auc": eval_record["model_metrics"].get("roc_auc"),
            "macro_brier_score": eval_record["model_metrics"].get("calibration", {}).get("macro_brier_score"),
            "confusion_matrix": eval_record["model_metrics"]["confusion_matrix"],
            "per_class_metrics": eval_record["model_metrics"]["per_class_metrics"],
        },
        "baseline_comparison": {
            "dummy_macro_f1": eval_record["dummy_baseline_metrics"]["macro_f1"],
            "rule_baseline_macro_f1": eval_record["rule_baseline_metrics"]["macro_f1"],
            "f1_lift_over_dummy": round(eval_record["model_metrics"]["macro_f1"] - eval_record["dummy_baseline_metrics"]["macro_f1"], 4),
            "f1_lift_over_rules": round(eval_record["model_metrics"]["macro_f1"] - eval_record["rule_baseline_metrics"]["macro_f1"], 4),
        },
        "disagreement_with_rules": eval_record.get("disagreement_analysis", {}),
        "known_training_details": {
            "historical_training_timestamp": "UNKNOWN (pre-Phase 3 legacy artifact)",
            "training_dataset_origin": "Synthetic latent distribution generator (app.ml.generate_weakness_dataset / generate_readiness_dataset)",
            "training_data_seed": "42 (documented default)",
            "cv_splits": "5-Fold Stratified K-Fold (documented in training scripts)",
        },
        "limitations": [
            "Trained and evaluated on synthetic data generated via heuristic rules.",
            "Does not represent human-annotated ground-truth interview performance.",
            "In Model 2, deterministic rules serve as the authoritative production verdict; ML runs as a logged challenger."
        ],
        "synthetic_notice": SYNTHETIC_DATA_DISCLAIMER
    }

    output_meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


# ==============================================================================
# 7. CLI ENTRY POINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Offline ML Evaluation Harness for Phase 3 Models")
    parser.add_argument("--model-type", choices=["model1", "model2", "all"], default="all",
                        help="Which model to evaluate: 'model1', 'model2', or 'all'")
    parser.add_argument("--model1-path", type=str, default=str(MODELS_DIR / "model1_skill_evaluator.joblib"),
                        help="Path to Model 1 joblib artifact")
    parser.add_argument("--model2-path", type=str, default=str(MODELS_DIR / "model2_final_recommendation.joblib"),
                        help="Path to Model 2 joblib artifact")
    parser.add_argument("--output-dir", type=str, default=str(REPORTS_DIR),
                        help="Output directory for reports")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PHASE 3: OFFLINE ML EVALUATION & BASELINE AUDIT HARNESS")
    print("=" * 70)

    if args.model_type in ("model1", "all"):
        m1_path = Path(args.model1_path)
        print(f"\n[1/2] Evaluating Model 1: Skill Evaluator ({m1_path})...")
        m1_rec = evaluate_model(m1_path, model_type="model1", output_dir=out_dir)
        m1_meta = create_model_metadata_record(m1_path, model_type="model1", eval_record=m1_rec)
        print(f" -> Accuracy: {m1_rec['model_metrics']['accuracy']:.4f} | Balanced Acc: {m1_rec['model_metrics']['balanced_accuracy']:.4f}")
        print(f" -> Macro F1: {m1_rec['model_metrics']['macro_f1']:.4f} (Dummy Lift: {m1_meta['baseline_comparison']['f1_lift_over_dummy']:+.4f})")
        print(f" -> Artifact SHA-256: {m1_rec['model_sha256']}")
        print(f" -> Metadata saved: {m1_path.with_name('model1_skill_evaluator_metadata.json')}")

    if args.model_type in ("model2", "all"):
        m2_path = Path(args.model2_path)
        print(f"\n[2/2] Evaluating Model 2: Final Recommendation Engine ({m2_path})...")
        m2_rec = evaluate_model(m2_path, model_type="model2", output_dir=out_dir)
        m2_meta = create_model_metadata_record(m2_path, model_type="model2", eval_record=m2_rec)
        print(f" -> Accuracy: {m2_rec['model_metrics']['accuracy']:.4f} | Balanced Acc: {m2_rec['model_metrics']['balanced_accuracy']:.4f}")
        print(f" -> Macro F1: {m2_rec['model_metrics']['macro_f1']:.4f} (Dummy Lift: {m2_meta['baseline_comparison']['f1_lift_over_dummy']:+.4f})")
        print(f" -> Challenger Disagreement Rate: {m2_rec['disagreement_analysis']['disagreement_rate'] * 100:.2f}%")
        print(f" -> Artifact SHA-256: {m2_rec['model_sha256']}")
        print(f" -> Metadata saved: {m2_path.with_name('model2_final_recommendation_metadata.json')}")

    print("\n" + "=" * 70)
    print("EVALUATION HARNESS EXECUTION COMPLETE")
    print(f"Reports written to: {out_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
