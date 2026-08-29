"""
PREDICTION UTILITY

Loads trained skill level model and provides an interface for making predictions
on new candidate skill feature records with input validation.
"""

from pathlib import Path
from typing import Dict, Any, List, Union
import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "skill_level_model.joblib"

REQUIRED_FEATURES = [
    "cv_matched",
    "required_level",
    "importance",
    "basic_score",
    "intermediate_score",
    "advanced_score",
    "total_score",
]

VALID_LEVELS = {"basic", "intermediate", "advanced"}


class SkillLevelPredictor:
    """
    Predictor wrapper class for the candidate skill proficiency ML model.
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self.pipeline = None
        self._load_model()

    def _load_model(self):
        """Loads the trained model pipeline from joblib file."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {self.model_path}. "
                "Please run 'python -m app.ml.train_model' first to train and save the model."
            )
        self.pipeline = joblib.load(self.model_path)

    @classmethod
    def validate_feature_dict(cls, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates input feature dictionary. Raises ValueError for missing or invalid values.
        """
        if not isinstance(feature_dict, dict):
            raise ValueError(f"Input must be a dictionary, got {type(feature_dict).__name__}")

        missing = [feat for feat in REQUIRED_FEATURES if feat not in feature_dict]
        if missing:
            raise ValueError(f"Missing required input features: {missing}")

        validated = {}
        
        # cv_matched
        cv_m = feature_dict["cv_matched"]
        if isinstance(cv_m, bool):
            validated["cv_matched"] = int(cv_m)
        elif isinstance(cv_m, (int, float)) and cv_m in (0, 1):
            validated["cv_matched"] = int(cv_m)
        else:
            raise ValueError(f"cv_matched must be boolean or 0/1, got {cv_m}")

        # required_level
        req_lvl = str(feature_dict["required_level"]).lower().strip()
        if req_lvl not in VALID_LEVELS:
            raise ValueError(f"required_level must be one of {VALID_LEVELS}, got '{req_lvl}'")
        validated["required_level"] = req_lvl

        # importance
        imp = str(feature_dict["importance"]).lower().strip()
        if not imp:
            raise ValueError("importance string cannot be empty")
        validated["importance"] = imp

        # score fields
        for score_key in ["basic_score", "intermediate_score", "advanced_score", "total_score"]:
            val = feature_dict[score_key]
            try:
                score_float = float(val)
            except (ValueError, TypeError):
                raise ValueError(f"{score_key} must be a numeric float, got {val}")
            
            if not (0.0 <= score_float <= 1.0):
                raise ValueError(f"{score_key} must be between 0.0 and 1.0, got {score_float}")
            validated[score_key] = score_float

        return validated

    def predict_single(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predicts skill proficiency level for a single candidate skill record.

        Parameters:
            feature_dict (dict): Feature key-values matching REQUIRED_FEATURES.

        Returns:
            dict: {
                "predicted_level": str ("basic"|"intermediate"|"advanced"),
                "probabilities": dict {class_name: float}
            }
        """
        validated = self.validate_feature_dict(feature_dict)
        df_input = pd.DataFrame([validated])[REQUIRED_FEATURES]
        
        predicted_class = str(self.pipeline.predict(df_input)[0])
        probabilities = {}
        if hasattr(self.pipeline, "predict_proba"):
            probs = self.pipeline.predict_proba(df_input)[0]
            classes = list(self.pipeline.classes_)
            probabilities = {cls_name: round(float(prob), 4) for cls_name, prob in zip(classes, probs)}

        return {
            "predicted_level": predicted_class,
            "probabilities": probabilities
        }

    def predict_batch(self, feature_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Predicts skill proficiency levels for a list of candidate skill records.
        """
        return [self.predict_single(feat) for feat in feature_list]


def predict_skill_level(feature_dict: Dict[str, Any], model_path: Path = DEFAULT_MODEL_PATH) -> str:
    """
    Convenience function to predict skill level string for a given feature dictionary.
    """
    predictor = SkillLevelPredictor(model_path=model_path)
    res = predictor.predict_single(feature_dict)
    return res["predicted_level"]


if __name__ == "__main__":
    import sys
    print("[SKILL LEVEL PREDICTOR TEST CLI]")
    sample_input = {
        "cv_matched": True,
        "required_level": "intermediate",
        "importance": "required",
        "basic_score": 0.95,
        "intermediate_score": 0.80,
        "advanced_score": 0.45,
        "total_score": 0.74
    }
    try:
        predictor = SkillLevelPredictor()
        res = predictor.predict_single(sample_input)
        print(f"Sample Input: {sample_input}")
        print(f"Prediction Result: {res}")
    except Exception as e:
        print(f"Error during prediction: {e}")
