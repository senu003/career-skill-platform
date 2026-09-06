"""
WEAKNESS ML TRAINING & EVALUATION EXPERIMENT MODULE

Implements a regularized baseline classifier (Logistic Regression + StandardScaler)
for controlled Weakness ML training and evaluation experiments (Step 3B).

METHODOLOGICAL NOTE:
Target label is deterministically defined as:
`is_weakness = 1 if level_gap > 0 OR total_score < 0.60 else 0`

Experiment A ('target_reconstruction_experiment') uses assessment performance variables
that reconstruct this deterministic rule.

Experiment B ('behavioral_experiment') tests whether non-target behavioral/timing and
aggregate candidate context features contain signal beyond the target-defining variables.

IMPORTANT:
This module is for offline experimentation only.
Do NOT integrate predictions into production APIs, assessment scoring, or database schemas.
Do NOT manufacture synthetic training data.
"""

from typing import List, Dict, Any, Union, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold
try:
    from sklearn.model_selection import StratifiedGroupKFold
    HAS_STRATIFIED_GROUP_KFOLD = True
except ImportError:
    HAS_STRATIFIED_GROUP_KFOLD = False

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score
)

from app.ml.weakness_labels import TARGET_LABEL_KEY

# Experiment A: Performance reconstruction experiment
EXPERIMENT_A_NAME = "target_reconstruction_experiment"
EXPERIMENT_A_FEATURES: List[str] = [
    "level_gap",
    "total_score",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "required_level",
    "assessed_level",
    "candidate_below_requirement_ratio",
]

# Experiment B: Behavioral & aggregate candidate context experiment
EXPERIMENT_B_NAME = "behavioral_experiment"
EXPERIMENT_B_FEATURES: List[str] = [
    "questions_answered_count",
    "avg_answer_time_seconds",
    "answer_time_std_seconds",
    "min_answer_time_seconds",
    "max_answer_time_seconds",
    "timed_questions_count",
    "candidate_avg_answer_time_seconds",
    "candidate_avg_total_score",
    "candidate_score_std",
]

# Explicitly forbidden features for Experiment B to prevent target leakage
FORBIDDEN_BEHAVIORAL_FEATURES: List[str] = [
    "level_gap",
    "total_score",
    "candidate_below_requirement_ratio",
    "required_level",
    "assessed_level",
    "basic_score",
    "intermediate_score",
    "advanced_score",
]

# Pure Behavioral Experiment: Response-process/timing features only
EXPERIMENT_PURE_BEHAVIORAL_NAME = "pure_behavioral_experiment"
EXPERIMENT_PURE_BEHAVIORAL_FEATURES: List[str] = [
    "questions_answered_count",
    "avg_answer_time_seconds",
    "answer_time_std_seconds",
    "min_answer_time_seconds",
    "max_answer_time_seconds",
    "timed_questions_count",
    "candidate_avg_answer_time_seconds",
]

# Explicitly forbidden features for Pure Behavioral experiment
FORBIDDEN_PURE_BEHAVIORAL_FEATURES: List[str] = [
    "level_gap",
    "total_score",
    "candidate_below_requirement_ratio",
    "required_level",
    "assessed_level",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "candidate_avg_total_score",
    "candidate_score_std",
]


def verify_feature_exclusions(
    feature_list: List[str],
    forbidden: List[str] = FORBIDDEN_BEHAVIORAL_FEATURES
) -> List[str]:
    """
    Checks if any forbidden target-defining features exist in the given feature list.
    Returns a list of violating feature names (empty if clean).
    """
    return [f for f in feature_list if f in forbidden]


def verify_pure_behavioral_exclusions(
    feature_list: List[str],
    forbidden: List[str] = FORBIDDEN_PURE_BEHAVIORAL_FEATURES
) -> List[str]:
    """
    Checks if any forbidden performance-representing features exist in the Pure Behavioral feature list.
    Returns a list of violating feature names (empty if clean).
    """
    return [f for f in feature_list if f in forbidden]


def compute_majority_baseline(
    dataset: List[Dict[str, Any]],
    target_key: str = TARGET_LABEL_KEY
) -> Dict[str, Any]:
    """
    Computes an explicit majority-class baseline evaluation on the given dataset.
    The majority class is determined dynamically (default weakness=1).
    All samples are predicted as the majority class.

    Parameters:
        dataset (list of dicts): Dataset records.
        target_key (str): Key name for target label.

    Returns:
        dict containing majority baseline evaluation metrics.
    """
    if not isinstance(dataset, list) or not dataset:
        return {
            "majority_class": 1,
            "sample_count": 0,
            "class_distribution": {0: 0, 1: 0},
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "roc_auc": None,
            "pr_auc": None,
            "note": "Empty dataset provided."
        }

    y_true = []
    for r in dataset:
        if target_key in r and r[target_key] is not None:
            try:
                y_true.append(int(r[target_key]))
            except (ValueError, TypeError):
                pass

    if not y_true:
        return {
            "majority_class": 1,
            "sample_count": 0,
            "class_distribution": {0: 0, 1: 0},
            "accuracy": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "roc_auc": None,
            "pr_auc": None,
            "note": f"Target key '{target_key}' missing or invalid in dataset."
        }

    counts = {0: y_true.count(0), 1: y_true.count(1)}
    majority_cls = 1 if counts[1] >= counts[0] else 0
    y_pred = [majority_cls] * len(y_true)

    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    pos_ratio = counts[1] / len(y_true) if len(y_true) > 0 else None

    return {
        "majority_class": majority_cls,
        "sample_count": len(y_true),
        "class_distribution": counts,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "roc_auc": 0.5000,
        "pr_auc": round(float(pos_ratio), 4) if pos_ratio is not None else None,
        "note": f"Majority baseline constantly predicting class {majority_cls}."
    }


def validate_training_dataset(
    dataset: List[Dict[str, Any]],
    target_key: str = TARGET_LABEL_KEY
) -> Tuple[bool, str, Dict[int, int]]:
    """
    Validates dataset before training:
    - Checks for non-empty input
    - Counts sample rows
    - Verifies at least 2 distinct target classes exist
    - Computes class distribution dict {0: count_0, 1: count_1}

    Parameters:
        dataset (list of dicts): Clean tabular dataset records.
        target_key (str): Key name for the target label.

    Returns:
        Tuple (is_valid, reason_message, class_distribution_dict)
    """
    if not isinstance(dataset, list) or len(dataset) == 0:
        return False, "Training dataset is empty (0 samples).", {0: 0, 1: 0}

    targets = []
    for record in dataset:
        if target_key in record and record[target_key] is not None:
            try:
                targets.append(int(record[target_key]))
            except (ValueError, TypeError):
                pass

    if len(targets) == 0:
        return False, f"Target key '{target_key}' missing or invalid in all records.", {0: 0, 1: 0}

    class_counts = {0: targets.count(0), 1: targets.count(1)}
    unique_classes = set(targets)

    if len(unique_classes) < 2:
        return (
            False,
            f"Cannot train classifier: dataset contains only 1 class ({unique_classes}). "
            "At least 2 distinct classes are required.",
            class_counts,
        )

    return True, "Dataset validation successful.", class_counts


def build_baseline_model(random_state: int = 42) -> Pipeline:
    """
    Builds a small, regularized baseline classifier pipeline (StandardScaler + L2 Logistic Regression).

    Parameters:
        random_state (int): Seed for reproducibility.

    Returns:
        sklearn.pipeline.Pipeline: Unfitted ML pipeline.
    """
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(
            C=1.0,
            solver="liblinear",
            random_state=random_state
        ))
    ])


def predict_weakness_probability(
    model: Any,
    features: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame, np.ndarray],
    feature_names: Optional[List[str]] = None
) -> Union[float, List[float]]:
    """
    Predicts weakness probability (class 1) for input feature vector(s).

    FOR EXPERIMENT EVALUATION ONLY. DO NOT INTEGRATE INTO PRODUCTION APIS.

    Parameters:
        model: Trained sklearn Pipeline or Classifier.
        features: Feature dictionary, list of dicts, DataFrame, or 2D array.
        feature_names (optional): Expected feature names ordering if dict is passed.

    Returns:
        float if single sample, or List[float] if multiple samples. Probabilities are in range [0.0, 1.0].
    """
    if model is None:
        raise ValueError("Cannot predict with uninitialized or None model.")

    # Convert input to DataFrame / 2D array format
    if isinstance(features, dict):
        if feature_names:
            row = [features.get(k, 0.0) for k in feature_names]
            X = np.array([row], dtype=float)
        else:
            X = np.array([list(features.values())], dtype=float)
        is_single = True
    elif isinstance(features, list) and len(features) > 0 and isinstance(features[0], dict):
        if feature_names:
            rows = [[r.get(k, 0.0) for k in feature_names] for r in features]
            X = np.array(rows, dtype=float)
        else:
            keys = list(features[0].keys())
            rows = [[r.get(k, 0.0) for k in keys] for r in features]
            X = np.array(rows, dtype=float)
        is_single = False
    elif isinstance(features, pd.DataFrame):
        X = features.to_numpy(dtype=float)
        is_single = len(features) == 1
    elif isinstance(features, np.ndarray):
        X = features.astype(float)
        is_single = (features.ndim == 1) or (features.shape[0] == 1)
        if features.ndim == 1:
            X = features.reshape(1, -1)
    else:
        raise TypeError(f"Unsupported feature input type for prediction: {type(features)}")

    # Handle predict_proba
    if not hasattr(model, "predict_proba"):
        raise AttributeError("Model does not support predict_proba.")

    probs = model.predict_proba(X)
    
    # Class 1 probability
    if probs.ndim == 2 and probs.shape[1] >= 2:
        class_1_probs = probs[:, 1].tolist()
    else:
        class_1_probs = probs.flatten().tolist()

    # Round probabilities safely to 4 decimal places
    class_1_probs = [round(float(p), 4) for p in class_1_probs]

    if is_single and len(class_1_probs) == 1:
        return class_1_probs[0]
    return class_1_probs


def run_weakness_experiment(
    dataset: List[Dict[str, Any]],
    experiment_type: str = "B",
    random_state: int = 42,
    target_key: str = TARGET_LABEL_KEY,
    use_group_cv: bool = False,
    groups: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Runs a complete controlled ML training experiment (Experiment A, B, or Pure Behavioral).

    Parameters:
        dataset (list of dicts): Clean tabular dataset records.
        experiment_type (str): 'A' for Experiment A (performance reconstruction);
                               'B' for Experiment B (behavioral & candidate context);
                               'PURE_BEHAVIORAL' for Pure Behavioral experiment (timing only).
        random_state (int): Random state for reproducibility.
        target_key (str): Key name for the target label.
        use_group_cv (bool): If True, use candidate/attempt group-aware cross validation.
        groups (list, optional): Candidate/attempt group IDs for each row. If None and use_group_cv=True,
                                 groups are extracted from record metadata keys (candidate_id, attempt_id, user_id).

    Returns:
        dict containing:
            - model: Trained baseline Pipeline fitted on all valid data
            - feature_names: List of feature keys used
            - metrics: Dict of calculated CV evaluation metrics
            - class_distribution: Dict {0: n0, 1: n1}
            - sample_count: int
            - experiment_name: str
            - warnings: List of str warnings/limitations
            - is_trainable: bool
            - is_group_cv: bool
    """
    # 1. Resolve experiment configuration
    exp_type_upper = str(experiment_type).strip().upper()
    if exp_type_upper in ("A", "TARGET_RECONSTRUCTION", "TARGET_RECONSTRUCTION_EXPERIMENT"):
        exp_name = EXPERIMENT_A_NAME
        feature_names = list(EXPERIMENT_A_FEATURES)
    elif exp_type_upper in ("B", "BEHAVIORAL", "BEHAVIORAL_EXPERIMENT"):
        exp_name = EXPERIMENT_B_NAME
        feature_names = list(EXPERIMENT_B_FEATURES)
        # Verify strict feature exclusion for Experiment B
        violating = verify_feature_exclusions(feature_names)
        if violating:
            raise ValueError(f"Experiment B feature set contains forbidden target-defining features: {violating}")
    elif exp_type_upper in ("PURE_BEHAVIORAL", "PURE_BEHAVIORAL_EXPERIMENT", "C"):
        exp_name = EXPERIMENT_PURE_BEHAVIORAL_NAME
        feature_names = list(EXPERIMENT_PURE_BEHAVIORAL_FEATURES)
        # Verify strict feature exclusion for Pure Behavioral
        violating = verify_pure_behavioral_exclusions(feature_names)
        if violating:
            raise ValueError(f"Pure Behavioral feature set contains forbidden performance features: {violating}")
    else:
        raise ValueError(f"Invalid experiment_type '{experiment_type}'. Must be 'A', 'B', or 'PURE_BEHAVIORAL'.")

    warnings_list: List[str] = [
        "Methodological Limitation: Baseline target is deterministically defined as "
        f"(is_weakness = 1 if level_gap > 0 OR total_score < 0.60 else 0). "
        "Models evaluate feature predictive signal against this target rule.",
        "Experimental Notice: Predictions are for evaluation only. Do NOT integrate into production APIs."
    ]

    # 2. Validate training data
    is_valid, reason, class_dist = validate_training_dataset(dataset, target_key=target_key)
    sample_count = len(dataset) if isinstance(dataset, list) else 0

    if not is_valid:
        raise ValueError(f"Dataset validation failed for {exp_name}: {reason}")

    if sample_count < 50:
        warnings_list.append(
            f"Dataset size ({sample_count} samples) is under 50. Treat results as exploratory."
        )

    # 3. Build X matrix, y vector, and group array safely (no dataset mutation)
    X_rows = []
    y_vals = []
    extracted_groups = []
    for idx, record in enumerate(dataset):
        row = [float(record.get(k, 0.0)) for k in feature_names]
        X_rows.append(row)
        y_vals.append(int(record[target_key]))

        # Group resolution hierarchy: candidate_id -> attempt_id -> user_id -> row_idx
        gid = record.get("candidate_id") or record.get("attempt_id") or record.get("user_id") or f"candidate_{idx}"
        extracted_groups.append(str(gid))

    X_arr = np.array(X_rows, dtype=float)
    y_arr = np.array(y_vals, dtype=int)

    if groups is not None and len(groups) == sample_count:
        group_arr = np.array([str(g) for g in groups])
    else:
        group_arr = np.array(extracted_groups)

    # 4. Fit baseline model on full dataset
    full_model = build_baseline_model(random_state=random_state)
    full_model.fit(X_arr, y_arr)

    # 5. Dynamic Cross-Validation (StratifiedKFold vs StratifiedGroupKFold)
    minority_count = min(class_dist.get(0, 0), class_dist.get(1, 0))
    n_unique_groups = len(set(group_arr))
    
    if use_group_cv:
        n_splits = min(5, minority_count, n_unique_groups)
    else:
        n_splits = min(5, minority_count)

    cv_metrics: Dict[str, Any] = {}

    if minority_count < 2 or n_splits < 2:
        warnings_list.append(
            f"Minority class count ({minority_count}) or unique groups ({n_unique_groups}) is less than 2. Cross-validation skipped."
        )
        cv_metrics = {
            "cv_folds": 0,
            "accuracy": round(float(accuracy_score(y_arr, full_model.predict(X_arr))), 4),
            "precision": round(float(precision_score(y_arr, full_model.predict(X_arr), zero_division=0)), 4),
            "recall": round(float(recall_score(y_arr, full_model.predict(X_arr), zero_division=0)), 4),
            "f1": round(float(f1_score(y_arr, full_model.predict(X_arr), zero_division=0)), 4),
            "roc_auc": None,
            "pr_auc": None,
            "is_group_cv": use_group_cv,
            "note": "Evaluated on full dataset without cross-validation due to insufficient minority class samples or groups."
        }
    else:
        if use_group_cv and HAS_STRATIFIED_GROUP_KFOLD:
            splitter = StratifiedGroupKFold(n_splits=n_splits)
            splits = splitter.split(X_arr, y_arr, group_arr)
        else:
            if use_group_cv and not HAS_STRATIFIED_GROUP_KFOLD:
                warnings_list.append("StratifiedGroupKFold not available in installed scikit-learn. Falling back to StratifiedKFold.")
            splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
            splits = splitter.split(X_arr, y_arr)

        accs, precs, recs, f1s = [], [], [], []
        roc_aucs, pr_aucs = [], []

        for train_idx, test_idx in splits:
            X_train, X_test = X_arr[train_idx], X_arr[test_idx]
            y_train, y_test = y_arr[train_idx], y_arr[test_idx]

            # Verify no group overlap if candidate group-aware
            if use_group_cv:
                train_groups = set(group_arr[train_idx])
                test_groups = set(group_arr[test_idx])
                overlap = train_groups.intersection(test_groups)
                if overlap:
                    raise RuntimeError(f"Group leakage detected in candidate-aware fold split: {overlap}")

            # Skip fold if train fold has only 1 class
            if len(np.unique(y_train)) < 2:
                maj_cls = int(np.bincount(y_train).argmax())
                y_pred = np.full_like(y_test, maj_cls)
                y_prob = np.full_like(y_test, float(maj_cls), dtype=float)
            else:
                fold_model = build_baseline_model(random_state=random_state)
                fold_model.fit(X_train, y_train)

                y_pred = fold_model.predict(X_test)
                y_prob = fold_model.predict_proba(X_test)[:, 1]

            accs.append(accuracy_score(y_test, y_pred))
            precs.append(precision_score(y_test, y_pred, zero_division=0))
            recs.append(recall_score(y_test, y_pred, zero_division=0))
            f1s.append(f1_score(y_test, y_pred, zero_division=0))

            # Safe ROC-AUC calculation
            if len(np.unique(y_test)) > 1 and len(np.unique(y_prob)) > 1:
                try:
                    roc_aucs.append(roc_auc_score(y_test, y_prob))
                except ValueError:
                    pass
                try:
                    pr_aucs.append(average_precision_score(y_test, y_prob))
                except ValueError:
                    pass

        def safe_mean(vals: List[float]) -> Optional[float]:
            return round(float(np.mean(vals)), 4) if vals else None

        cv_metrics = {
            "cv_folds": n_splits,
            "accuracy": safe_mean(accs),
            "precision": safe_mean(precs),
            "recall": safe_mean(recs),
            "f1": safe_mean(f1s),
            "roc_auc": safe_mean(roc_aucs),
            "pr_auc": safe_mean(pr_aucs),
            "is_group_cv": use_group_cv,
        }

    return {
        "model": full_model,
        "feature_names": feature_names,
        "metrics": cv_metrics,
        "class_distribution": class_dist,
        "sample_count": sample_count,
        "unique_group_count": n_unique_groups,
        "experiment_name": exp_name,
        "warnings": warnings_list,
        "is_trainable": True,
        "is_group_cv": use_group_cv,
    }
