"""
MODEL 2: FINAL JOB RECOMMENDATION PREDICTION UTILITY

Loads trained Model 2 artifact and provides robust prediction interface for overall
candidate readiness with deterministic safety boundaries and transparent skill priority ranking.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib
import pandas as pd
import numpy as np

from app.ml.readiness_features import (
    extract_model2_features,
    compute_priority_skills,
    MODEL2_FEATURES
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "model2_final_recommendation.joblib"

VERDICT_CATEGORIES = ["Interview Ready", "Short-Term Prep", "Major Upskill Required"]


class Model2FinalRecommendationPredictor:
    """
    Predictor wrapper class for Model 2: Final Recommendation Engine.
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self.pipeline = None
        self._load_model()

    def _load_model(self):
        """Loads trained pipeline or trains a fallback pipeline if artifact is missing."""
        if not self.model_path.exists():
            try:
                from app.ml.train_readiness_model import train_and_evaluate_model2
                metrics, self.pipeline = train_and_evaluate_model2(model_output_path=self.model_path)
            except Exception:
                self.pipeline = None
        else:
            try:
                self.pipeline = joblib.load(self.model_path)
            except Exception:
                self.pipeline = None

    def _apply_safety_layer(
        self,
        raw_verdict: str,
        confidence: float,
        features: Dict[str, float]
    ) -> tuple[str, float]:
        """
        DETERMINISTIC SAFETY LAYER (Section 14)

        Validates ML model predictions against deterministic boundaries to prevent
        nonsensical results on synthetic edge cases.
        """
        total = max(1.0, features.get("total_required_skills", 1.0))
        missing = features.get("missing_skills_count", 0.0)
        missing_ratio = missing / total
        avg_gap = features.get("average_skill_gap", 0.0)
        relearn_count = features.get("relearn_basics_count", 0.0)
        upgrade_count = features.get("upgrade_needed_count", 0.0)
        accuracy = features.get("overall_assessment_accuracy", 0.0)
        mastered_count = features.get("mastered_count", 0.0)

        adjusted_verdict = raw_verdict
        adjusted_conf = confidence

        # Safety Rule 1: Candidate missing all or almost all required skills cannot be Interview Ready
        if missing_ratio >= 0.75 and raw_verdict == "Interview Ready":
            adjusted_verdict = "Major Upskill Required"
            adjusted_conf = 0.90

        # Safety Rule 2: High level gap or multiple relearn skills cannot be Interview Ready
        elif (avg_gap >= 1.8 or relearn_count >= 2) and raw_verdict == "Interview Ready":
            if missing_ratio >= 0.4 or avg_gap >= 2.2:
                adjusted_verdict = "Major Upskill Required"
            else:
                adjusted_verdict = "Short-Term Prep"
            adjusted_conf = 0.85

        # Safety Rule 3: Multiple upgrade needed skills cannot be Interview Ready
        elif upgrade_count >= 3 and raw_verdict == "Interview Ready":
            adjusted_verdict = "Short-Term Prep"
            adjusted_conf = 0.82

        # Safety Rule 4: Strong candidate with 0 missing skills, 0 level gap, high accuracy cannot be Major Upskill Required
        elif missing == 0 and avg_gap == 0.0 and (accuracy >= 0.75 or mastered_count >= 1) and raw_verdict == "Major Upskill Required":
            if accuracy >= 0.80 or mastered_count >= 2:
                adjusted_verdict = "Interview Ready"
            else:
                adjusted_verdict = "Short-Term Prep"
            adjusted_conf = 0.88

        return adjusted_verdict, round(adjusted_conf, 4)

    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts final overall recommendation verdict, confidence score, and top priority skills.

        Parameters:
            input_data (dict): Either combined_analysis dictionary or feature dictionary.

        Returns:
            dict: {
                "final_verdict": str ("Interview Ready" | "Short-Term Prep" | "Major Upskill Required"),
                "confidence": float (0.0 to 1.0),
                "priority_skills": List[dict]
            }
        """
        # Determine if input_data is already features or combined_analysis
        if all(k in input_data for k in MODEL2_FEATURES):
            features = {k: float(input_data[k]) for k in MODEL2_FEATURES}
            raw_skills = input_data.get("skills", [])
        else:
            features = extract_model2_features(input_data)
            raw_skills = input_data.get("skills")
            if raw_skills is None:
                matched_input = input_data.get("matched_skills", [])
                missing_input = input_data.get("missing_skills", [])
                raw_skills = (matched_input if isinstance(matched_input, list) else []) + \
                             (missing_input if isinstance(missing_input, list) else [])

        # Model Prediction with Safe Fallback
        if self.pipeline is not None:
            try:
                df_feat = pd.DataFrame([features])[MODEL2_FEATURES]
                raw_verdict = str(self.pipeline.predict(df_feat)[0])

                if hasattr(self.pipeline, "predict_proba"):
                    probs = self.pipeline.predict_proba(df_feat)[0]
                    raw_conf = float(np.max(probs))
                else:
                    raw_conf = 0.85
            except Exception:
                raw_verdict, raw_conf = self._rule_based_fallback(features)
        else:
            raw_verdict, raw_conf = self._rule_based_fallback(features)

        # Apply Safety Layer
        final_verdict, confidence = self._apply_safety_layer(raw_verdict, raw_conf, features)

        # Calculate Priority Skills Ranking
        priority_skills = compute_priority_skills(raw_skills, top_n=5)

        return {
            "final_verdict": final_verdict,
            "confidence": confidence,
            "priority_skills": priority_skills
        }

    def _rule_based_fallback(self, features: Dict[str, float]) -> tuple[str, float]:
        """Transparent rule-based fallback if ML pipeline is unavailable."""
        total = max(1.0, features.get("total_required_skills", 1.0))
        missing = features.get("missing_skills_count", 0.0)
        missing_ratio = missing / total
        avg_gap = features.get("average_skill_gap", 0.0)
        accuracy = features.get("overall_assessment_accuracy", 0.0)

        if missing_ratio <= 0.15 and avg_gap <= 0.35 and (accuracy >= 0.70 or features.get("mastered_count", 0.0) >= 1):
            return "Interview Ready", 0.85
        elif missing_ratio >= 0.50 or avg_gap >= 1.75:
            return "Major Upskill Required", 0.88
        else:
            return "Short-Term Prep", 0.80


def predict_final_recommendation(
    input_data: Dict[str, Any],
    model_path: Path = DEFAULT_MODEL_PATH
) -> Dict[str, Any]:
    """
    Convenience function to run Model 2 Final Recommendation prediction.
    """
    predictor = Model2FinalRecommendationPredictor(model_path=model_path)
    return predictor.predict(input_data)
