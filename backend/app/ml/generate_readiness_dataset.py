"""
MODEL 2: SYNTHETIC READINESS DATASET GENERATOR

Generates synthetic candidate-job analysis records for training and evaluating
Model 2: Final Job Recommendation Engine.

NOTE: This dataset contains SYNTHETIC DEVELOPMENT DATA ONLY and must NOT be represented
or treated as real candidate data.

Target categories:
- 'Interview Ready'
- 'Short-Term Prep'
- 'Major Upskill Required'
"""

from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from app.ml.readiness_features import extract_model2_features, MODEL2_FEATURES

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "model2_readiness_dataset.csv"

VERDICT_CATEGORIES = ["Interview Ready", "Short-Term Prep", "Major Upskill Required"]
SAMPLE_SKILL_NAMES = ["Python", "SQL", "FastAPI", "Docker", "Git", "React", "PostgreSQL", "AWS"]
SKILL_LEVELS = ["basic", "intermediate", "advanced"]


def _simulate_candidate_analysis(tier: str) -> Dict[str, Any]:
    """
    Simulates raw per-skill evaluation structures for a candidate belonging to a latent tier.
    """
    num_skills = int(np.random.randint(4, 9))
    selected_skills = np.random.choice(SAMPLE_SKILL_NAMES, size=min(num_skills, len(SAMPLE_SKILL_NAMES)), replace=False)

    skills_data = []
    missing_skills = []
    matched_skills = []

    for skill_name in selected_skills:
        importance = "required" if np.random.random() < 0.70 else "preferred"
        req_level = np.random.choice(SKILL_LEVELS, p=[0.3, 0.5, 0.2])

        if tier == "strong":
            matched = bool(np.random.random() < 0.92)
            assessed = bool(np.random.random() < 0.85)
            score = float(np.clip(np.random.normal(0.88, 0.07), 0.60, 1.0)) if assessed else None
            ml_pred = np.random.choice(["intermediate", "advanced"], p=[0.3, 0.7]) if assessed else None
            gap = 0 if assessed else None
            model1_rec = np.random.choice(["Mastered", "Speed Practice", "Upgrade Needed"], p=[0.75, 0.20, 0.05]) if assessed else None
        elif tier == "moderate":
            matched = bool(np.random.random() < 0.70)
            assessed = bool(np.random.random() < 0.70)
            score = float(np.clip(np.random.normal(0.68, 0.12), 0.35, 0.90)) if assessed else None
            ml_pred = np.random.choice(["basic", "intermediate", "advanced"], p=[0.3, 0.5, 0.2]) if assessed else None
            gap = int(np.random.choice([0, 1, 2], p=[0.5, 0.4, 0.1])) if assessed else None
            model1_rec = np.random.choice(["Mastered", "Upgrade Needed", "Speed Practice", "Re-learn Basics"], p=[0.3, 0.4, 0.2, 0.1]) if assessed else None
        else:  # weak
            matched = bool(np.random.random() < 0.40)
            assessed = bool(np.random.random() < 0.50)
            score = float(np.clip(np.random.normal(0.42, 0.15), 0.10, 0.70)) if assessed else None
            ml_pred = np.random.choice(["basic", "intermediate"], p=[0.7, 0.3]) if assessed else None
            gap = int(np.random.choice([1, 2, 3], p=[0.4, 0.4, 0.2])) if assessed else None
            model1_rec = np.random.choice(["Upgrade Needed", "Re-learn Basics", "Speed Practice"], p=[0.5, 0.4, 0.1]) if assessed else None

        item = {
            "skill": skill_name,
            "required_level": req_level,
            "importance": importance,
            "matched": matched,
            "assessed_level": ml_pred,
            "ml_predicted_level": ml_pred,
            "level_gap": gap,
            "total_score": round(score, 4) if score is not None else None,
            "skill_recommendation": model1_rec,
            "recommendation_confidence": round(float(np.random.uniform(0.70, 0.95)), 2) if model1_rec else None
        }
        skills_data.append(item)
        if matched:
            matched_skills.append(item)
        else:
            missing_skills.append(item)

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skills": skills_data
    }


def compute_composite_verdict_target(features: Dict[str, float]) -> str:
    """
    Computes a realistic non-trivial target label for Model 2 readiness classification.

    Formula:
        score = 0.30 * (1 - missing_ratio)
              + 0.30 * (1 - normalized_gap)
              + 0.20 * assessment_accuracy
              + 0.10 * (mastered_ratio)
              - 0.10 * (relearn_ratio + 0.5 * upgrade_ratio)
              + N(0, 0.05^2)
    """
    total = max(1.0, features.get("total_required_skills", 1.0))
    missing = features.get("missing_skills_count", 0.0)
    missing_ratio = min(1.0, missing / total)

    avg_gap = features.get("average_skill_gap", 0.0)
    norm_gap = min(1.0, avg_gap / 3.0)

    accuracy = features.get("overall_assessment_accuracy", 0.0)
    mastered = features.get("mastered_count", 0.0) / total
    relearn = features.get("relearn_basics_count", 0.0) / total
    upgrade = features.get("upgrade_needed_count", 0.0) / total

    composite = (
        0.30 * (1.0 - missing_ratio)
        + 0.30 * (1.0 - norm_gap)
        + 0.20 * accuracy
        + 0.10 * mastered
        - 0.10 * (relearn + 0.5 * upgrade)
    )

    noise = np.random.normal(0.0, 0.05)
    final_score = float(np.clip(composite + noise, 0.0, 1.0))

    if final_score >= 0.70:
        return "Interview Ready"
    elif final_score >= 0.45:
        return "Short-Term Prep"
    else:
        return "Major Upskill Required"


def generate_model2_dataset(num_samples: int = 600, random_seed: int = 42) -> pd.DataFrame:
    """
    Generates a synthetic dataset for training Model 2.
    """
    np.random.seed(random_seed)

    tiers = ["strong", "moderate", "weak"]
    samples_per_tier = num_samples // len(tiers)
    remainder = num_samples % len(tiers)

    latent_tiers = []
    for t in tiers:
        latent_tiers.extend([t] * samples_per_tier)
    for i in range(remainder):
        latent_tiers.append(tiers[i])

    np.random.shuffle(latent_tiers)

    rows = []
    for tier in latent_tiers:
        analysis = _simulate_candidate_analysis(tier)
        feats = extract_model2_features(analysis)
        target = compute_composite_verdict_target(feats)

        row = {k: feats[k] for k in MODEL2_FEATURES}
        row["target"] = target
        rows.append(row)

    df = pd.DataFrame(rows)
    return df[MODEL2_FEATURES + ["target"]]


def main():
    print("[SYNTHETIC MODEL 2 READINESS DATASET GENERATOR]")
    print("Generating synthetic development dataset...")
    df = generate_model2_dataset(num_samples=600, random_seed=42)

    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEFAULT_OUTPUT_PATH, index=False)
    print(f"Dataset successfully created at: {DEFAULT_OUTPUT_PATH}")
    print(f"Shape: {df.shape}")
    print("\nTarget Class Distribution:")
    print(df["target"].value_counts())


if __name__ == "__main__":
    main()
