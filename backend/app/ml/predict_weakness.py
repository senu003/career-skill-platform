"""
MODEL 1: SKILL EVALUATOR PREDICTION UTILITY

Loads trained Model 1 artifact and provides robust interface for making predictions
with automatic feature engineering and safe fallbacks for missing telemetry data.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import joblib
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "model1_skill_evaluator.joblib"

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

LEVEL_MAP = {"basic": 1, "intermediate": 2, "advanced": 3}


def level_to_numeric(level_val: Optional[Union[str, int]]) -> int:
    if level_val is None:
        return 0
    if isinstance(level_val, (int, float)):
        return int(level_val) if 0 <= int(level_val) <= 3 else 0
    clean = str(level_val).lower().strip()
    return LEVEL_MAP.get(clean, 0)


class Model1SkillEvaluator:
    """
    Predictor wrapper class for Model 1: Skill Evaluator.
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self.pipeline = None
        self._load_model()

    def _load_model(self):
        """Loads trained pipeline, or trains a fallback pipeline if missing."""
        if not self.model_path.exists():
            from app.ml.train_weakness_model import train_and_evaluate_model1
            metrics, self.pipeline = train_and_evaluate_model1(model_output_path=self.model_path)
        else:
            self.pipeline = joblib.load(self.model_path)

    @classmethod
    def prepare_features(cls, input_dict: Dict[str, Any]) -> Dict[str, float]:
        """
        Derives and formats all 12 Model 1 features safely from candidate attempt data.
        Handles missing timing, missing CV level, and missing scores robustly.
        """
        req_numeric = level_to_numeric(input_dict.get("jd_required_level") or input_dict.get("required_level"))
        if req_numeric == 0:
            req_numeric = 1  # Default to basic if unspecified

        cv_numeric = level_to_numeric(input_dict.get("cv_parsed_level") or input_dict.get("cv_level"))
        assessed_numeric = level_to_numeric(input_dict.get("assessed_level"))

        b_score = float(np.clip(input_dict.get("basic_score", 0.0), 0.0, 1.0))
        i_score = float(np.clip(input_dict.get("intermediate_score", 0.0), 0.0, 1.0))
        a_score = float(np.clip(input_dict.get("advanced_score", 0.0), 0.0, 1.0))

        # Overall assessment score
        raw_assessment_score = input_dict.get("assessment_score") or input_dict.get("total_score")
        if raw_assessment_score is None:
            assessment_score = float(np.clip((0.35 * b_score) + (0.40 * i_score) + (0.25 * a_score), 0.0, 1.0))
        else:
            assessment_score = float(np.clip(raw_assessment_score, 0.0, 1.0))

        # Timing telemetry
        raw_avg_time = input_dict.get("avg_time_per_question")
        if raw_avg_time is not None and float(raw_avg_time) > 0:
            avg_time = float(raw_avg_time)
        else:
            avg_time = 30.0  # Documented safe fallback reference time

        raw_rel_time = input_dict.get("relative_time")
        if raw_rel_time is not None and float(raw_rel_time) > 0:
            relative_time = float(raw_rel_time)
        else:
            relative_time = round(avg_time / 30.0, 4)

        # Attempt tracking
        attempt_count = max(1, int(input_dict.get("attempt_count", 1)))
        prev_best = input_dict.get("previous_best_score")
        if prev_best is not None:
            previous_best_score = float(np.clip(prev_best, 0.0, 1.0))
        else:
            previous_best_score = assessment_score

        # score_gap (required - assessed)
        raw_gap = input_dict.get("score_gap")
        if raw_gap is not None:
            score_gap = float(max(0, raw_gap))
        else:
            score_gap = float(max(0, req_numeric - assessed_numeric))

        # speed_accuracy signal
        raw_speed_acc = input_dict.get("speed_accuracy")
        if raw_speed_acc is not None:
            speed_accuracy = float(raw_speed_acc)
        else:
            speed_factor = 1.0 / (1.0 + max(0.0, (avg_time - 30.0) / 30.0))
            speed_accuracy = round(assessment_score * speed_factor, 4)

        return {
            "jd_required_level": float(req_numeric),
            "cv_parsed_level": float(cv_numeric),
            "basic_score": b_score,
            "intermediate_score": i_score,
            "advanced_score": a_score,
            "assessment_score": assessment_score,
            "avg_time_per_question": avg_time,
            "relative_time": relative_time,
            "attempt_count": float(attempt_count),
            "previous_best_score": previous_best_score,
            "score_gap": score_gap,
            "speed_accuracy": speed_accuracy,
        }

    def predict_single(self, input_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts Model 1 recommendation and confidence score for a candidate skill record.

        Returns:
            dict: {
                "recommendation": str ("Mastered"|"Upgrade Needed"|"Speed Practice"|"Re-learn Basics"),
                "confidence": float (0.0 to 1.0)
            }
        """
        features = self.prepare_features(input_dict)
        df_input = pd.DataFrame([features])[MODEL1_FEATURES]

        recommendation = str(self.pipeline.predict(df_input)[0])

        confidence = 0.85
        if hasattr(self.pipeline, "predict_proba"):
            probs = self.pipeline.predict_proba(df_input)[0]
            max_prob = float(np.max(probs))
            confidence = round(max_prob, 4)

        return {
            "recommendation": recommendation,
            "confidence": confidence
        }


def predict_skill_evaluator(
    input_dict: Dict[str, Any],
    model_path: Path = DEFAULT_MODEL_PATH
) -> Dict[str, Any]:
    """
    Convenience function to run Model 1 Skill Evaluator prediction.
    """
    evaluator = Model1SkillEvaluator(model_path=model_path)
    return evaluator.predict_single(input_dict)
