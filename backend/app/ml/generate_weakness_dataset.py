"""
MODEL 1: SKILL EVALUATOR DATASET GENERATOR

Generates synthetic dataset for Model 1 Skill Evaluator training.
Contains feature columns:
- jd_required_level (1=basic, 2=intermediate, 3=advanced)
- cv_parsed_level (0=none/unmatched, 1=basic, 2=intermediate, 3=advanced)
- basic_score (0.0 to 1.0)
- intermediate_score (0.0 to 1.0)
- advanced_score (0.0 to 1.0)
- assessment_score (0.0 to 1.0)
- avg_time_per_question (seconds)
- relative_time (avg_time_per_question / reference 30.0s)
- attempt_count (1 to 5)
- previous_best_score (0.0 to 1.0)
- score_gap (required_level_numeric - assessed_level_numeric)
- speed_accuracy (combined signal from correctness & timing)
- target ("Mastered", "Upgrade Needed", "Speed Practice", "Re-learn Basics")

NOTE:
If labels are generated from heuristic bootstrap logic, this script explicitly isolates
it as an initial/bootstrap labeling strategy for synthetic development data.
"""

from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "model1_weakness_dataset.csv"

LEVEL_ENCODING = {"basic": 1, "intermediate": 2, "advanced": 3, "none": 0}
TARGET_CLASSES = ["Mastered", "Upgrade Needed", "Speed Practice", "Re-learn Basics"]


def encode_level(level_str: str) -> int:
    if not level_str:
        return 0
    return LEVEL_ENCODING.get(str(level_str).lower().strip(), 0)


def generate_model1_dataset(num_samples: int = 1000, random_seed: int = 42) -> pd.DataFrame:
    """
    Generates synthetic candidate skill evaluation dataset with Model 1 feature structure.
    """
    np.random.seed(random_seed)
    records: List[Dict[str, Any]] = []

    # Distribute samples across latent profiles
    profiles = ["mastered", "upgrade", "speed_practice", "relearn"]
    samples_per_profile = num_samples // len(profiles)

    for profile in profiles:
        for _ in range(samples_per_profile):
            req_numeric = int(np.random.choice([1, 2, 3]))
            cv_numeric = int(np.random.choice([0, 1, 2, 3]))
            attempt_count = int(np.random.choice([1, 2, 3, 4, 5], p=[0.5, 0.25, 0.15, 0.07, 0.03]))

            if profile == "mastered":
                b_score = float(np.clip(np.random.normal(0.92, 0.05), 0.70, 1.0))
                i_score = float(np.clip(np.random.normal(0.85, 0.08), 0.60, 1.0)) if req_numeric >= 2 else float(np.clip(np.random.normal(0.85, 0.1), 0.5, 1.0))
                a_score = float(np.clip(np.random.normal(0.80, 0.10), 0.50, 1.0)) if req_numeric == 3 else float(np.clip(np.random.normal(0.60, 0.15), 0.2, 1.0))
                avg_time = float(np.clip(np.random.normal(25.0, 5.0), 10.0, 40.0))
                assessed_numeric = req_numeric
                target_label = "Mastered"

            elif profile == "speed_practice":
                b_score = float(np.clip(np.random.normal(0.90, 0.06), 0.75, 1.0))
                i_score = float(np.clip(np.random.normal(0.82, 0.08), 0.65, 1.0)) if req_numeric >= 2 else 0.75
                a_score = float(np.clip(np.random.normal(0.78, 0.10), 0.55, 1.0)) if req_numeric == 3 else 0.50
                avg_time = float(np.clip(np.random.normal(55.0, 10.0), 42.0, 90.0))
                assessed_numeric = req_numeric
                target_label = "Speed Practice"

            elif profile == "upgrade":
                b_score = float(np.clip(np.random.normal(0.75, 0.10), 0.50, 0.95))
                i_score = float(np.clip(np.random.normal(0.55, 0.12), 0.30, 0.75))
                a_score = float(np.clip(np.random.normal(0.35, 0.12), 0.10, 0.55))
                avg_time = float(np.clip(np.random.normal(32.0, 8.0), 15.0, 60.0))
                assessed_numeric = max(1, req_numeric - 1)
                target_label = "Upgrade Needed"

            else:  # relearn
                b_score = float(np.clip(np.random.normal(0.35, 0.12), 0.0, 0.55))
                i_score = float(np.clip(np.random.normal(0.20, 0.10), 0.0, 0.40))
                a_score = float(np.clip(np.random.normal(0.10, 0.08), 0.0, 0.30))
                avg_time = float(np.clip(np.random.normal(40.0, 12.0), 15.0, 80.0))
                assessed_numeric = 0
                target_label = "Re-learn Basics"

            # Derived overall assessment score
            raw_assessment_score = (0.35 * b_score) + (0.40 * i_score) + (0.25 * a_score) + np.random.normal(0.0, 0.01)
            assessment_score = float(np.clip(raw_assessment_score, 0.0, 1.0))

            # Previous best score
            if attempt_count > 1:
                prev_best = float(np.clip(assessment_score + np.random.uniform(-0.15, 0.10), 0.0, 1.0))
            else:
                prev_best = assessment_score

            # Derived features
            score_gap = max(0, req_numeric - assessed_numeric)
            relative_time = round(avg_time / 30.0, 4)

            # Combined speed_accuracy signal
            speed_factor = 1.0 / (1.0 + max(0.0, (avg_time - 30.0) / 30.0))
            speed_accuracy = round(assessment_score * speed_factor, 4)

            records.append({
                "jd_required_level": req_numeric,
                "cv_parsed_level": cv_numeric,
                "basic_score": round(b_score, 4),
                "intermediate_score": round(i_score, 4),
                "advanced_score": round(a_score, 4),
                "assessment_score": round(assessment_score, 4),
                "avg_time_per_question": round(avg_time, 2),
                "relative_time": relative_time,
                "attempt_count": attempt_count,
                "previous_best_score": round(prev_best, 4),
                "score_gap": score_gap,
                "speed_accuracy": speed_accuracy,
                "target": target_label
            })

    df = pd.DataFrame(records)
    return df


def main():
    print("[MODEL 1 DATASET GENERATOR]")
    print("Generating bootstrap synthetic dataset for Model 1: Skill Evaluator...")
    df = generate_model1_dataset(num_samples=1000, random_seed=42)
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEFAULT_OUTPUT_PATH, index=False)
    print(f"Dataset successfully created at: {DEFAULT_OUTPUT_PATH}")
    print(f"Dataset shape: {df.shape}")
    print("\nTarget class distribution:")
    print(df["target"].value_counts())
    print("\nFirst 5 rows:")
    print(df.head())


if __name__ == "__main__":
    main()
