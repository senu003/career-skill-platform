"""
SYNTHETIC DEVELOPMENT DATA GENERATOR

This script generates synthetic candidate-skill records for training a skill proficiency level ML model.
NOTE: This dataset contains SYNTHETIC DEVELOPMENT DATA ONLY and must NOT be represented or treated as real candidate data.
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd

# Define paths relative to backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "skill_training_data.csv"

# Target levels and probabilities
LEVELS = ["basic", "intermediate", "advanced"]
IMPORTANCE_CHOICES = ["required", "preferred"]


def generate_synthetic_dataset(num_samples: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """
    Generates a synthetic dataset of candidate-skill records.

    Parameters:
        num_samples (int): Total number of rows to generate (default ~500).
        random_seed (int): Seed for reproducibility.

    Returns:
        pd.DataFrame: DataFrame containing feature columns and 'target_level'.
    """
    np.random.seed(random_seed)

    # Balance samples evenly across latent levels
    samples_per_level = num_samples // len(LEVELS)
    remainder = num_samples % len(LEVELS)
    
    latent_levels = []
    for level in LEVELS:
        latent_levels.extend([level] * samples_per_level)
    for i in range(remainder):
        latent_levels.append(LEVELS[i])
        
    np.random.shuffle(latent_levels)

    data = []
    for latent_ability in latent_levels:
        req_level = np.random.choice(LEVELS)
        importance = np.random.choice(IMPORTANCE_CHOICES, p=[0.65, 0.35])

        # Generate CV matching probability based on latent ability vs required level
        if latent_ability == "basic":
            match_prob = 0.60 if req_level == "basic" else (0.35 if req_level == "intermediate" else 0.15)
            basic_score = np.random.normal(0.70, 0.12)
            inter_score = np.random.normal(0.32, 0.14)
            adv_score = np.random.normal(0.12, 0.10)
        elif latent_ability == "intermediate":
            match_prob = 0.85 if req_level == "basic" else (0.70 if req_level == "intermediate" else 0.40)
            basic_score = np.random.normal(0.90, 0.08)
            inter_score = np.random.normal(0.75, 0.10)
            adv_score = np.random.normal(0.38, 0.14)
        else:  # advanced
            match_prob = 0.95 if req_level == "basic" else (0.88 if req_level == "intermediate" else 0.78)
            basic_score = np.random.normal(0.96, 0.04)
            inter_score = np.random.normal(0.88, 0.08)
            adv_score = np.random.normal(0.80, 0.10)

        cv_matched = bool(np.random.random() < match_prob)

        # Clip scores to [0.0, 1.0] and round
        basic_score = float(np.clip(basic_score, 0.0, 1.0))
        inter_score = float(np.clip(inter_score, 0.0, 1.0))
        adv_score = float(np.clip(adv_score, 0.0, 1.0))

        # Total score calculation with noise
        raw_total = (0.35 * basic_score) + (0.40 * inter_score) + (0.25 * adv_score) + np.random.normal(0.0, 0.02)
        total_score = float(np.clip(raw_total, 0.0, 1.0))

        data.append({
            "cv_matched": cv_matched,
            "required_level": req_level,
            "importance": importance,
            "basic_score": round(basic_score, 4),
            "intermediate_score": round(inter_score, 4),
            "advanced_score": round(adv_score, 4),
            "total_score": round(total_score, 4),
            "target_level": latent_ability
        })

    df = pd.DataFrame(data)
    return df


def main():
    print("[SYNTHETIC DATASET GENERATOR]")
    print("NOTE: Generating SYNTHETIC DEVELOPMENT DATA ONLY. Not real candidate data.")

    df = generate_synthetic_dataset(num_samples=500, random_seed=42)
    
    # Ensure destination directory exists
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(DEFAULT_OUTPUT_PATH, index=False)
    print(f"Dataset successfully created at: {DEFAULT_OUTPUT_PATH}")
    print(f"Dataset shape: {df.shape}")
    print("\nClass distribution:")
    print(df["target_level"].value_counts())
    print("\nFirst 5 rows:")
    print(df.head())


if __name__ == "__main__":
    main()
