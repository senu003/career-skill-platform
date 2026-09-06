"""
SYNTHETIC OVERALL JOB READINESS DATASET GENERATOR

This script generates synthetic candidate-job analysis records for training and testing
an Overall Job Readiness ML model.

NOTE: This dataset contains SYNTHETIC DEVELOPMENT DATA ONLY and must NOT be represented
or treated as real candidate data.

LABEL GENERATION METHODOLOGY:
-----------------------------
To ensure synthetic labels reflect realistic overall candidate readiness without being a
trivial direct copy of any single feature, labels ('low', 'medium', 'high') are generated
via a multi-factor composite readiness score that combines 6 key feature signals:

1. required_skills_match_ratio (weight: 0.25) - Match ratio of required job skills from CV.
2. avg_assessment_score (weight: 0.25)        - Average candidate score across technical assessments.
3. cv_matching_score (weight: 0.20)           - Overall CV keyword/vector similarity score.
4. ml_meets_req_ratio (weight: 0.15)          - Fraction of skills where ML predicted level meets job required level.
5. zero_gap_skills_ratio (weight: 0.15)       - Fraction of assessed skills with zero level gap.
6. avg_level_gap penalty (weight: -0.10)       - Penalty proportional to normalized average skill level gap.

Gaussian noise (std = 0.04) is added to model real-world variances (e.g. interview performance jitter).
Final composite scores map to overall readiness categories:
- 'high'   : composite_score >= 0.70
- 'medium' : 0.45 <= composite_score < 0.70
- 'low'    : composite_score < 0.45
"""

import os
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from app.ml.overall_features import build_overall_features, DEFAULT_FEATURE_KEYS

# Define paths relative to backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "overall_training_data.csv"

# Target levels and Latent Profile Tiers
READINESS_LEVELS = ["low", "medium", "high"]
SKILL_LEVELS = ["basic", "intermediate", "advanced"]
SAMPLE_SKILL_NAMES = ["Python", "SQL", "FastAPI", "Docker", "Git", "React", "PostgreSQL", "AWS"]


def _generate_candidate_skills(tier: str) -> List[Dict[str, Any]]:
    """
    Simulates raw per-skill evaluation structures for a candidate belonging to a latent tier.
    """
    num_skills = int(np.random.randint(3, 8))
    selected_skills = np.random.choice(SAMPLE_SKILL_NAMES, size=min(num_skills, len(SAMPLE_SKILL_NAMES)), replace=False)

    skills_data = []
    for skill_name in selected_skills:
        importance = "required" if np.random.random() < 0.65 else "preferred"
        req_level = np.random.choice(SKILL_LEVELS, p=[0.4, 0.4, 0.2])

        if tier == "high":
            matched = bool(np.random.random() < 0.90)
            assessed = bool(np.random.random() < 0.85)
            score = float(np.clip(np.random.normal(0.85, 0.08), 0.50, 1.0)) if assessed else None
            ml_pred = np.random.choice(["intermediate", "advanced"], p=[0.3, 0.7]) if assessed else None
            gap = 0 if assessed else None
        elif tier == "medium":
            matched = bool(np.random.random() < 0.65)
            assessed = bool(np.random.random() < 0.60)
            score = float(np.clip(np.random.normal(0.65, 0.12), 0.30, 0.90)) if assessed else None
            ml_pred = np.random.choice(["basic", "intermediate", "advanced"], p=[0.3, 0.5, 0.2]) if assessed else None
            gap = int(np.random.choice([0, 1], p=[0.6, 0.4])) if assessed else None
        else:  # low
            matched = bool(np.random.random() < 0.35)
            assessed = bool(np.random.random() < 0.40)
            score = float(np.clip(np.random.normal(0.40, 0.14), 0.10, 0.70)) if assessed else None
            ml_pred = np.random.choice(["basic", "intermediate"], p=[0.7, 0.3]) if assessed else None
            gap = int(np.random.choice([1, 2], p=[0.6, 0.4])) if assessed else None

        skill_item = {
            "skill": skill_name,
            "required_level": req_level,
            "importance": importance,
            "matched": matched,
            "assessed_level": ml_pred,
            "ml_predicted_level": ml_pred,
            "level_gap": gap,
            "total_score": round(score, 4) if score is not None else None
        }
        skills_data.append(skill_item)

    return skills_data


def compute_synthetic_target_label(features: Dict[str, float]) -> str:
    """
    Computes a non-trivial synthetic ground-truth target label ('low', 'medium', 'high')
    from the extracted feature dictionary using a weighted composite formula + noise.

    Formula:
      composite_score = 0.25 * required_skills_match_ratio
                      + 0.25 * avg_assessment_score
                      + 0.20 * cv_matching_score
                      + 0.15 * ml_meets_req_ratio
                      + 0.15 * zero_gap_skills_ratio
                      - 0.10 * min(avg_level_gap / 3.0, 1.0)
                      + N(0, 0.04^2)
    """
    req_match = features.get("required_skills_match_ratio", 0.0)
    avg_score = features.get("avg_assessment_score", 0.0)
    cv_score = features.get("cv_matching_score", 0.0)
    ml_meets = features.get("ml_meets_req_ratio", 0.0)
    zero_gap = features.get("zero_gap_skills_ratio", 0.0)
    avg_gap = features.get("avg_level_gap", 0.0)

    # Normalized gap penalty [0.0, 1.0]
    gap_penalty = min(avg_gap / 3.0, 1.0)

    # Weighted sum
    composite = (
        0.25 * req_match
        + 0.25 * avg_score
        + 0.20 * cv_score
        + 0.15 * ml_meets
        + 0.15 * zero_gap
        - 0.10 * gap_penalty
    )

    # Stochastic realistic jitter
    noise = np.random.normal(0.0, 0.04)
    final_score = float(np.clip(composite + noise, 0.0, 1.0))

    if final_score >= 0.70:
        return "high"
    elif final_score >= 0.45:
        return "medium"
    else:
        return "low"


def generate_overall_dataset(num_samples: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """
    Generates a reproducible synthetic dataset of candidate overall readiness records.

    Parameters:
        num_samples (int): Total number of rows to generate (default 500).
        random_seed (int): Seed for numpy random generator reproducibility.

    Returns:
        pd.DataFrame: DataFrame containing all 14 feature columns plus 'overall_readiness' target.
    """
    np.random.seed(random_seed)

    # Balanced latent tiers across dataset
    tiers = ["low", "medium", "high"]
    samples_per_tier = num_samples // len(tiers)
    remainder = num_samples % len(tiers)

    latent_tiers = []
    for tier in tiers:
        latent_tiers.extend([tier] * samples_per_tier)
    for i in range(remainder):
        latent_tiers.append(tiers[i])

    np.random.shuffle(latent_tiers)

    rows = []
    for latent_tier in latent_tiers:
        skills = _generate_candidate_skills(latent_tier)

        # Baseline CV score corresponding to latent tier
        if latent_tier == "high":
            raw_cv = float(np.clip(np.random.normal(88.0, 7.0), 60.0, 100.0))
        elif latent_tier == "medium":
            raw_cv = float(np.clip(np.random.normal(65.0, 10.0), 35.0, 85.0))
        else:
            raw_cv = float(np.clip(np.random.normal(40.0, 12.0), 10.0, 70.0))

        combined_analysis = {
            "skills": skills,
            "score_data": {"score": round(raw_cv, 2)}
        }

        # Extract strict 14 features using build_overall_features
        features = build_overall_features(combined_analysis)

        # Compute synthetic composite target label
        target_label = compute_synthetic_target_label(features)

        row = {k: features[k] for k in DEFAULT_FEATURE_KEYS}
        row["overall_readiness"] = target_label
        rows.append(row)

    df = pd.DataFrame(rows)

    # Reorder columns explicitly: 14 features + overall_readiness
    column_order = list(DEFAULT_FEATURE_KEYS) + ["overall_readiness"]
    df = df[column_order]

    return df


def generate_synthetic_overall_dataset(num_samples: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """Alias for generate_overall_dataset."""
    return generate_overall_dataset(num_samples=num_samples, random_seed=random_seed)


def main():
    print("[SYNTHETIC OVERALL READINESS DATASET GENERATOR]")
    print("NOTE: Generating SYNTHETIC DEVELOPMENT DATA ONLY. Not real candidate data.")

    df = generate_overall_dataset(num_samples=500, random_seed=42)

    # Ensure destination data directory exists
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df.to_csv(DEFAULT_OUTPUT_PATH, index=False)
    print(f"Overall readiness dataset successfully created at: {DEFAULT_OUTPUT_PATH}")
    print(f"Dataset shape: {df.shape}")
    print("\nClass distribution ('overall_readiness'):")
    print(df["overall_readiness"].value_counts())
    print("\nFirst 5 rows:")
    print(df.head())


if __name__ == "__main__":
    main()
