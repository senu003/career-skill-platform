import logging
from sqlalchemy.orm import Session
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
import numpy as np

from app.ml.longitudinal_dataset import build_longitudinal_dataset
from app.ml.longitudinal_features import extract_features

logger = logging.getLogger(__name__)

class InsufficientTrainingDataError(Exception):
    """Raised when there is insufficient data or only one class in the target."""
    pass

def validate_dataset(X: pd.DataFrame, y: pd.Series):
    """
    Validates dataset before training.
    """
    if len(X) < 10:
        raise InsufficientTrainingDataError(f"Insufficient training data: only {len(X)} samples available.")
    
    if y.nunique() < 2:
        raise InsufficientTrainingDataError(f"Insufficient training data: target has {y.nunique()} classes (needs 2).")

def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
    }
    
    # Try ROC-AUC
    try:
        y_prob = model.predict_proba(X_test)[:, 1]
        metrics["roc_auc"] = roc_auc_score(y_test, y_prob)
    except Exception:
        metrics["roc_auc"] = None
        
    return metrics

def train_longitudinal_model(db: Session):
    """
    Builds data, extracts features, validates, and trains the longitudinal model.
    Will legitimately fail with InsufficientTrainingDataError if classes are missing.
    """
    # 1. Build dataset
    df = build_longitudinal_dataset(db)
    
    if df.empty:
        logger.info("INSUFFICIENT_DATA_FOR_TRAINING")
        raise InsufficientTrainingDataError("No longitudinal data available.")
        
    # 2. Target
    y = df["improved"].astype(int)
    
    # 3. Features
    X = extract_features(df)
    
    # 4. Validate
    try:
        validate_dataset(X, y)
    except InsufficientTrainingDataError as e:
        logger.info("INSUFFICIENT_DATA_FOR_TRAINING")
        raise e
        
    # 5. Preprocessing
    num_cols = ["previous_total_score", "previous_basic_score", "previous_intermediate_score", "previous_advanced_score", "days_since_previous"]
    cat_cols = ["previous_required_level", "previous_assessed_level", "previous_level_gap"]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols)
        ],
        remainder="passthrough"
    )
    
    # Features dropping non-predictive IDs
    X_trainable = X.drop(columns=["user_id", "skill"], errors="ignore")
    
    # 6. Candidate-aware Validation
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X_trainable, y, groups=X["user_id"]))
    
    X_train, X_test = X_trainable.iloc[train_idx], X_trainable.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # 7. Baseline Model
    lr_model = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", LogisticRegression(random_state=42, max_iter=1000))
    ])
    
    rf_model = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(random_state=42, n_estimators=100))
    ])
    
    lr_model.fit(X_train, y_train)
    rf_model.fit(X_train, y_train)
    
    lr_eval = evaluate_model(lr_model, X_test, y_test)
    rf_eval = evaluate_model(rf_model, X_test, y_test)
    
    # Do NOT save a .joblib model yet until data is proven sufficient and performant
    
    return {
        "status": "SUCCESS",
        "samples": len(X),
        "positive_class_ratio": float(np.mean(y)),
        "logistic_regression": lr_eval,
        "random_forest": rf_eval
    }
