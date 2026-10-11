"""
MODEL 2: FINAL JOB RECOMMENDATION PREDICTION UTILITY

Restructured to use Deterministic Rules as the primary path, with ML as a logged challenger.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import joblib
import pandas as pd
import numpy as np
import logging

from app.ml.readiness_features import (
    extract_model2_features,
    compute_priority_skills,
    MODEL2_FEATURES
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "model2_final_recommendation.joblib"

VERDICT_CATEGORIES = ["Interview Ready", "Short-Term Prep", "Major Upskill Required"]


class Model2FinalRecommendationPredictor:
    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.model_path = Path(model_path)
        self.pipeline = None
        self._load_model()

    def _load_model(self):
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

    def _deterministic_verdict(self, features: Dict[str, float], raw_skills: Optional[List[Dict[str, Any]]] = None) -> tuple[str, float]:
        """Primary rule-based verdict logic."""
        if not raw_skills:
            # Fallback if raw_skills not provided
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

        LEVEL_MAP = {'basic': 1, 'intermediate': 2, 'advanced': 3}
        failed_count = 0
        required_count = 0
        has_critical_failure = False

        for s in raw_skills:
            imp = str(s.get('importance', '')).lower()
            if 'required' not in imp and 'critical' not in imp:
                continue

            required_count += 1
            req_level = s.get('required_level', s.get('level', 'unspecified'))
            score = s.get('total_score')
            assessed_level = s.get('assessed_level')
            matched = s.get('matched', True)

            failed = False
            if not matched and score is None:
                failed = True
            elif score is not None:
                if score < 0.40:
                    failed = True
                else:
                    if LEVEL_MAP.get(str(req_level).lower(), 0) > 0 and LEVEL_MAP.get(str(assessed_level).lower(), 0) > 0:
                        if LEVEL_MAP.get(str(req_level).lower(), 0) - LEVEL_MAP.get(str(assessed_level).lower(), 0) >= 2:
                            failed = True

            if failed:
                failed_count += 1
                if 'critical' in imp:
                    has_critical_failure = True

        missing = features.get("missing_skills_count", 0.0)
        total = max(1.0, features.get("total_required_skills", 1.0))
        if missing / total >= 0.75:
            return "Major Upskill Required", 0.95

        if required_count == 0:
            return "Interview Ready", 0.85

        share = failed_count / required_count
        if share <= 0.20 and not has_critical_failure:
            return "Interview Ready", 0.85
        elif share <= 0.40:
            return "Short-Term Prep", 0.80
        else:
            return "Major Upskill Required", 0.88

    def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
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

        # Primary deterministic path
        rules_verdict, rules_conf = self._deterministic_verdict(features, raw_skills=raw_skills)

        # Challenger ML path
        ml_verdict = None
        ml_conf = None
        if self.pipeline is not None:
            try:
                df_feat = pd.DataFrame([features])[MODEL2_FEATURES]
                ml_verdict = str(self.pipeline.predict(df_feat)[0])
                if hasattr(self.pipeline, "predict_proba"):
                    probs = self.pipeline.predict_proba(df_feat)[0]
                    ml_conf = float(np.max(probs))
            except Exception as e:
                logger.error(f"ML Challenger Failed: {e}")

        # Log ML overrides/disagreements
        if ml_verdict and ml_verdict != rules_verdict:
            logger.info(f"ML Challenger override attempt: ML predicted '{ml_verdict}', Rules said '{rules_verdict}'. Currently ignoring ML.")
            ml_override_attempted = True
        else:
            ml_override_attempted = False

        # Final verdict defaults to rules unless ML is proven on eval harness
        # (For now, rules win as requested)
        final_verdict = rules_verdict
        confidence = rules_conf

        priority_skills = compute_priority_skills(raw_skills, top_n=5, gaps_only=True)
        readiness_reasons = generate_readiness_reasons(final_verdict, features, raw_skills=raw_skills)

        return {
            "final_verdict": final_verdict,
            "readiness_verdict": final_verdict,
            "readiness_reasons": readiness_reasons,
            "rules_verdict": rules_verdict,
            "ml_verdict": ml_verdict,
            "confidence": confidence,
            "ml_override_attempted": ml_override_attempted,
            "priority_skills": priority_skills
        }


def generate_readiness_reasons(
    verdict: str,
    features: Dict[str, float],
    raw_skills: Optional[List[Dict[str, Any]]] = None
) -> List[str]:
    """
    Generates 2-3 plain-language reasons explaining the candidate's job readiness verdict.
    """
    reasons: List[str] = []
    
    if raw_skills:
        # Count REQUIRED skills only (exclude preferred)
        req_skills = [
            s for s in raw_skills
            if (s.get("importance") or "required").strip().lower() != "preferred"
        ]
        total = len(req_skills)
        missing = sum(
            1 for s in req_skills
            if not s.get("matched", True) or s.get("cv_match_status") == "Missing"
        )
        matched = max(0, total - missing)
    else:
        total = int(features.get("total_required_skills", 0))
        missing = int(features.get("missing_skills_count", 0))
        matched = max(0, total - missing)

    # 1. Plain-language required skill coverage
    if total > 0:
        if missing == 0:
            reasons.append(f"Strong qualification match: all {total} required skills were identified in your CV evidence.")
        else:
            reasons.append(f"Found evidence for {matched} of {total} required skills directly in your CV.")
    else:
        reasons.append("Skills evaluated against provided job requirements.")

    # 2. Key gaps or strengths identified
    missing_skill_names: List[str] = []
    if raw_skills:
        for s in raw_skills:
            if not s.get("matched", True) or s.get("cv_match_status") == "Missing":
                name = s.get("skill")
                if name and name not in missing_skill_names:
                    missing_skill_names.append(name)

    if missing_skill_names:
        displayed_names = ", ".join(missing_skill_names[:2])
        if len(missing_skill_names) > 2:
            reasons.append(f"Skill gaps identified in {displayed_names} and {len(missing_skill_names) - 2} other area(s).")
        else:
            reasons.append(f"Skill gap identified in {displayed_names}; targeted practice recommended.")
    else:
        reasons.append("No critical qualification gaps identified across the required core competencies.")

    # 3. Verdict-specific plain-language guidance
    verdict_clean = (verdict or "").lower()
    if "interview ready" in verdict_clean:
        reasons.append("Candidate demonstrates high proficiency alignment; ready to proceed to technical interviews.")
    elif "major upskill" in verdict_clean:
        reasons.append("Foundational upskilling and structured learning recommended prior to technical interviews.")
    else:
        reasons.append("Targeted practice on identified skill gaps will quickly improve candidate match readiness.")

    return reasons[:3]


def predict_final_recommendation(
    input_data: Dict[str, Any],
    model_path: Path = DEFAULT_MODEL_PATH
) -> Dict[str, Any]:
    predictor = Model2FinalRecommendationPredictor(model_path=model_path)
    return predictor.predict(input_data)
