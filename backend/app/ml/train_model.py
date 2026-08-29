"""
MODEL TRAINING SCRIPT

Trains a classification model (Random Forest pipeline) to predict candidate skill level (basic, intermediate, advanced).
Reports cross-validation metrics, untouched test-set evaluation metrics (accuracy, precision, recall, F1, confusion matrix),
and saves the trained scikit-learn Pipeline artifact to models/skill_level_model.joblib.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support

from app.ml.generate_dataset import generate_synthetic_dataset

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "skill_training_data.csv"
DEFAULT_MODEL_DIR = BASE_DIR / "models"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "skill_level_model.joblib"

FEATURE_COLUMNS = [
    "cv_matched",
    "required_level",
    "importance",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "total_score",
]

TARGET_COLUMN = "target_level"
CLASSES = ["basic", "intermediate", "advanced"]


def build_pipeline(classifier=None) -> Pipeline:
    """
    Builds a scikit-learn Pipeline with preprocessing and specified classifier.
    By default uses RandomForestClassifier, but accepts any scikit-learn compatible estimator.
    """
    if classifier is None:
        classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42,
            class_weight="balanced"
        )

    categorical_features = ["required_level", "importance"]
    numerical_features = ["basic_score", "intermediate_score", "advanced_score", "total_score"]
    passthrough_features = ["cv_matched"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
            ("num", StandardScaler(), numerical_features),
            ("pass", "passthrough", passthrough_features),
        ]
    )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", classifier)
    ])

    return pipeline


def train_and_evaluate(
    data_path: Path = DEFAULT_DATA_PATH,
    model_output_path: Path = DEFAULT_MODEL_PATH,
    random_seed: int = 42
) -> Dict[str, Any]:
    """
    Loads data, trains model with Stratified CV, evaluates on untouched test set, and saves model.
    """
    if not data_path.exists():
        print(f"Dataset not found at {data_path}. Generating synthetic dataset...")
        df = generate_synthetic_dataset(num_samples=500, random_seed=random_seed)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
    else:
        df = pd.read_csv(data_path)

    X = df[FEATURE_COLUMNS].copy()
    # Ensure cv_matched is boolean or numeric
    X["cv_matched"] = X["cv_matched"].astype(int)
    y = df[TARGET_COLUMN].astype(str)

    # 1. Stratified Train / Test Split (keep test set untouched until final evaluation)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_seed, stratify=y
    )

    # 2. Build model pipeline
    pipeline = build_pipeline()

    # 3. Stratified Cross-Validation on training set
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
    cv_results = cross_validate(
        pipeline, X_train, y_train, cv=skf, scoring=["accuracy", "f1_macro"]
    )
    cv_mean_acc = float(np.mean(cv_results["test_accuracy"]))
    cv_std_acc = float(np.std(cv_results["test_accuracy"]))
    cv_mean_f1 = float(np.mean(cv_results["test_f1_macro"]))

    # 4. Train pipeline on full training set
    pipeline.fit(X_train, y_train)

    # 5. Final Evaluation on untouched Test Set
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
    report = classification_report(y_test, y_pred, target_names=CLASSES, output_dict=True)

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
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "model_path": str(model_output_path)
    }

    return metrics, pipeline


def main():
    print("[SKILL LEVEL ML MODEL TRAINING]")
    print(f"Loading data and training model...")

    metrics, _ = train_and_evaluate()

    print("\n" + "=" * 50)
    print("TRAINING & EVALUATION RESULTS")
    print("=" * 50)
    print(f"Dataset Total Rows : {metrics['dataset_size']}")
    print(f"Train Rows         : {metrics['train_size']}")
    print(f"Test Rows          : {metrics['test_size']}")
    print(f"5-Fold CV Accuracy : {metrics['cv_accuracy_mean']:.4f} (+/- {metrics['cv_accuracy_std']:.4f})")
    print(f"5-Fold CV Macro F1 : {metrics['cv_f1_macro_mean']:.4f}")
    print("-" * 50)
    print("UNTOUCHED TEST SET METRICS:")
    print(f"Accuracy  : {metrics['test_accuracy']:.4f}")
    print(f"Precision : {metrics['test_precision_macro']:.4f} (macro)")
    print(f"Recall    : {metrics['test_recall_macro']:.4f} (macro)")
    print(f"F1-Score  : {metrics['test_f1_macro']:.4f} (macro)")
    print("\nConfusion Matrix (labels = basic, intermediate, advanced):")
    cm = np.array(metrics['confusion_matrix'])
    print(f"               Pred Basic  Pred Inter  Pred Adv")
    for idx, class_name in enumerate(CLASSES):
        print(f"True {class_name:<10}: {cm[idx][0]:<10} {cm[idx][1]:<10} {cm[idx][2]:<10}")

    print("\nClassification Report:")
    report_df = pd.DataFrame(metrics['classification_report']).transpose()
    print(report_df.to_string())
    print("-" * 50)
    print(f"Model saved to: {metrics['model_path']}")


if __name__ == "__main__":
    main()
