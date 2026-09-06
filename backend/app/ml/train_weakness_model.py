"""
MODEL 1: SKILL EVALUATOR TRAINING & EVALUATION SCRIPT

Trains Model 1: Skill Evaluator to predict candidate skill recommendations:
- Mastered
- Upgrade Needed
- Speed Practice
- Re-learn Basics

Evaluates model with Stratified Train/Test split and Cross-Validation.
Reports Accuracy, Precision, Recall, F1, Confusion Matrix, and ROC-AUC.
Saves model artifact to models/model1_skill_evaluator.joblib.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
    roc_auc_score
)

from app.ml.generate_weakness_dataset import generate_model1_dataset

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "model1_weakness_dataset.csv"
DEFAULT_MODEL_DIR = BASE_DIR / "models"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "model1_skill_evaluator.joblib"

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

TARGET_CLASSES = ["Mastered", "Upgrade Needed", "Speed Practice", "Re-learn Basics"]


def build_model1_pipeline(classifier=None) -> Pipeline:
    """
    Builds Model 1 ML pipeline (StandardScaler + RandomForestClassifier).
    """
    if classifier is None:
        classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42,
            class_weight="balanced"
        )

    pipeline = Pipeline(steps=[
        ("scaler", StandardScaler()),
        ("classifier", classifier)
    ])
    return pipeline


def train_and_evaluate_model1(
    data_path: Path = DEFAULT_DATA_PATH,
    model_output_path: Path = DEFAULT_MODEL_PATH,
    random_seed: int = 42
) -> Tuple[Dict[str, Any], Pipeline]:
    """
    Trains Model 1 Skill Evaluator on dataset, evaluates performance, and saves model pipeline.
    """
    if not data_path.exists():
        print(f"Dataset not found at {data_path}. Generating dataset...")
        df = generate_model1_dataset(num_samples=1000, random_seed=random_seed)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
    else:
        df = pd.read_csv(data_path)

    X = df[MODEL1_FEATURES].copy()
    y = df["target"].astype(str)

    # 1. Stratified Train / Test Split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_seed, stratify=y
    )

    # 2. Build model pipeline
    pipeline = build_model1_pipeline()

    # 3. Stratified Cross-Validation on training set
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
    cv_results = cross_validate(
        pipeline, X_train, y_train, cv=skf, scoring=["accuracy", "f1_macro"]
    )
    cv_mean_acc = float(np.mean(cv_results["test_accuracy"]))
    cv_std_acc = float(np.std(cv_results["test_accuracy"]))
    cv_mean_f1 = float(np.mean(cv_results["test_f1_macro"]))

    # 4. Fit pipeline on full training set
    pipeline.fit(X_train, y_train)

    # 5. Evaluate on untouched Test Set
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test) if hasattr(pipeline, "predict_proba") else None

    acc = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=TARGET_CLASSES)
    report = classification_report(y_test, y_pred, target_names=TARGET_CLASSES, output_dict=True)

    roc_auc = None
    if y_proba is not None and len(np.unique(y_test)) == len(TARGET_CLASSES):
        try:
            roc_auc = float(roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro"))
        except Exception:
            roc_auc = None

    # 6. Save model artifact
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_output_path)

    metrics = {
        "dataset_size": len(df),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "cv_accuracy_mean": cv_mean_acc,
        "cv_accuracy_std": cv_std_acc,
        "cv_f1_macro_mean": cv_mean_f1,
        "test_accuracy": float(acc),
        "test_precision_macro": float(precision),
        "test_recall_macro": float(recall),
        "test_f1_macro": float(f1),
        "roc_auc": roc_auc,
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "model_path": str(model_output_path)
    }

    return metrics, pipeline


def main():
    print("[MODEL 1: SKILL EVALUATOR TRAINING]")
    metrics, _ = train_and_evaluate_model1()

    print("\n" + "=" * 55)
    print("TRAINING & EVALUATION METRICS")
    print("=" * 55)
    print(f"Dataset Size      : {metrics['dataset_size']}")
    print(f"Train Rows        : {metrics['train_size']}")
    print(f"Test Rows         : {metrics['test_size']}")
    print(f"5-Fold CV Acc     : {metrics['cv_accuracy_mean']:.4f} (+/- {metrics['cv_accuracy_std']:.4f})")
    print(f"5-Fold CV Macro F1: {metrics['cv_f1_macro_mean']:.4f}")
    print("-" * 55)
    print("UNTOUCHED TEST SET METRICS:")
    print(f"Accuracy         : {metrics['test_accuracy']:.4f}")
    print(f"Precision (macro): {metrics['test_precision_macro']:.4f}")
    print(f"Recall (macro)   : {metrics['test_recall_macro']:.4f}")
    print(f"F1-Score (macro) : {metrics['test_f1_macro']:.4f}")
    if metrics['roc_auc'] is not None:
        print(f"ROC-AUC (OVR)    : {metrics['roc_auc']:.4f}")

    print("\nConfusion Matrix (labels =", TARGET_CLASSES, "):")
    cm = np.array(metrics['confusion_matrix'])
    for idx, class_name in enumerate(TARGET_CLASSES):
        row_str = " ".join([f"{val:<8}" for val in cm[idx]])
        print(f"True {class_name:<16}: {row_str}")

    print("\nClassification Report:")
    report_df = pd.DataFrame(metrics['classification_report']).transpose()
    print(report_df.to_string())
    print("-" * 55)
    print(f"Model saved to: {metrics['model_path']}")


if __name__ == "__main__":
    main()
