"""
LONGITUDINAL ML INFERENCE SERVICE (STEP 13)

Provides isolated inference for predicting candidate skill improvement probability
based on pre-t1 historical assessment information (t0).

- Loads longitudinal_improvement_model.joblib once.
- Strictly audits for pre-t1 feature compliance (no t1 signal leakage).
- Returns probability of improvement (0.0 <= p <= 1.0) or None when history is insufficient/unavailable.
- Handles model loading and runtime errors safely without interrupting production requests.
"""

import os
import json
import joblib
import logging
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_FILE_PATH = os.path.join(BASE_DIR, "models", "longitudinal_improvement_model.joblib")
METADATA_FILE_PATH = os.path.join(BASE_DIR, "models", "longitudinal_improvement_model_metadata.json")

# Schema Constants
LEVEL_NUMERIC_MAP = {
    "basic": 1,
    "intermediate": 2,
    "advanced": 3,
    "1": 1,
    "2": 2,
    "3": 3,
    1: 1,
    2: 2,
    3: 3,
}

PRIORITY_FORMAT_MAP = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}

CATEGORICAL_FEATURES = [
    "previous_assessed_level",
    "required_level",
    "previous_priority",
]

NUMERICAL_FEATURES = [
    "previous_total_score",
    "previous_level_gap",
    "cv_match_score",
    "previous_is_weakness",
    "days_between_attempts",
    "previous_basic_score",
    "previous_intermediate_score",
    "previous_advanced_score",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERICAL_FEATURES

FORBIDDEN_T1_SUBSTRINGS = [
    "later_score",
    "later_total_score",
    "later_level",
    "later_weakness",
    "later_assessed_level",
    "improved",
    "declined",
    "score_change",
    "level_change",
    "persistent_weakness",
]


class LongitudinalImprovementPredictor:
    """Singleton inference wrapper for longitudinal skill improvement model."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LongitudinalImprovementPredictor, cls).__new__(cls)
            cls._instance._init_model()
        return cls._instance

    def _init_model(self):
        self.model = None
        self.metadata = None
        try:
            if os.path.exists(MODEL_FILE_PATH):
                self.model = joblib.load(MODEL_FILE_PATH)
                logger.info(f"Loaded longitudinal improvement model from {MODEL_FILE_PATH}")
            else:
                logger.warning(f"Longitudinal model file not found at {MODEL_FILE_PATH}")

            if os.path.exists(METADATA_FILE_PATH):
                with open(METADATA_FILE_PATH, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load longitudinal improvement model: {e}")
            self.model = None

    @classmethod
    def audit_t0_feature_leakage(cls, feature_dict: Dict[str, Any]):
        """Ensures zero t1 signal or forbidden target keys exist in input dict."""
        for key in feature_dict.keys():
            key_lower = str(key).lower()
            for forbidden in FORBIDDEN_T1_SUBSTRINGS:
                if forbidden in key_lower:
                    raise ValueError(
                        f"Data leakage detected in inference call: key '{key}' contains t1 signal ('{forbidden}')."
                    )

    def predict_probability(self, t0_features: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Calculates improvement probability for a given t0 feature dictionary.
        Returns float between 0.0 and 1.0, or None if input is invalid or model unavailable.
        """
        if not t0_features or not isinstance(t0_features, dict):
            return None

        if self.model is None:
            logger.warning("Predictor model is not loaded. Returning None.")
            return None

        try:
            # 1. Audit feature dict for t1 leakage
            self.audit_t0_feature_leakage(t0_features)

            # 2. Extract and validate raw features
            prev_assessed = t0_features.get("previous_assessed_level")
            req_level = t0_features.get("required_level")
            prev_priority = t0_features.get("previous_priority", "Medium")

            if prev_assessed is None or req_level is None:
                return None

            prev_assessed_num = LEVEL_NUMERIC_MAP.get(str(prev_assessed).lower().strip() if isinstance(prev_assessed, str) else prev_assessed)
            req_level_num = LEVEL_NUMERIC_MAP.get(str(req_level).lower().strip() if isinstance(req_level, str) else req_level)

            if prev_assessed_num is None or req_level_num is None:
                return None

            formatted_priority = PRIORITY_FORMAT_MAP.get(str(prev_priority), "Medium")

            # Score extraction and scale normalization (0-1 -> 0-100 if needed)
            def normalize_score(val: Optional[Any], default: float = 50.0) -> float:
                if val is None:
                    return default
                try:
                    num_val = float(val)
                    if 0.0 <= num_val <= 1.0 and num_val != 0.0:
                        return num_val * 100.0
                    return num_val
                except (ValueError, TypeError):
                    return default

            prev_total_score = normalize_score(t0_features.get("previous_total_score"))
            prev_basic_score = normalize_score(t0_features.get("previous_basic_score"))
            prev_intermediate_score = normalize_score(t0_features.get("previous_intermediate_score"))
            prev_advanced_score = normalize_score(t0_features.get("previous_advanced_score"))
            cv_match_score = normalize_score(t0_features.get("cv_match_score"), default=100.0 if t0_features.get("cv_matched") else 0.0)

            # Level gap
            calc_level_gap = max(0, req_level_num - prev_assessed_num)
            level_gap = int(t0_features.get("previous_level_gap", calc_level_gap))

            # Is weakness
            is_weakness_val = t0_features.get("previous_is_weakness")
            if isinstance(is_weakness_val, bool):
                prev_is_weakness = 1 if is_weakness_val else 0
            elif isinstance(is_weakness_val, (int, float)):
                prev_is_weakness = 1 if is_weakness_val > 0 else 0
            else:
                prev_is_weakness = 1 if (level_gap > 0 or prev_total_score < 70.0) else 0

            # Days between attempts
            days_val = t0_features.get("days_between_attempts", 30.0)
            try:
                days_between_attempts = max(0.0, float(days_val))
            except (ValueError, TypeError):
                days_between_attempts = 30.0

            # 3. Construct single-row DataFrame matching training feature columns
            row_dict = {
                "previous_assessed_level": prev_assessed_num,
                "required_level": req_level_num,
                "previous_priority": formatted_priority,
                "previous_total_score": prev_total_score,
                "previous_level_gap": level_gap,
                "cv_match_score": cv_match_score,
                "previous_is_weakness": prev_is_weakness,
                "days_between_attempts": days_between_attempts,
                "previous_basic_score": prev_basic_score,
                "previous_intermediate_score": prev_intermediate_score,
                "previous_advanced_score": prev_advanced_score,
            }

            df_input = pd.DataFrame([row_dict], columns=FEATURE_COLUMNS)

            # 4. Predict probability
            probs = self.model.predict_proba(df_input)
            prob_improved = float(probs[0][1])

            # Bound probability between 0.0 and 1.0
            bounded_prob = max(0.0, min(1.0, prob_improved))
            return round(bounded_prob, 4)

        except Exception as e:
            logger.warning(f"Error during longitudinal model prediction: {e}")
            return None


def predict_improvement_probability(t0_features: Optional[Dict[str, Any]]) -> Optional[float]:
    """Helper module function for longitudinal improvement prediction."""
    predictor = LongitudinalImprovementPredictor()
    return predictor.predict_probability(t0_features)
