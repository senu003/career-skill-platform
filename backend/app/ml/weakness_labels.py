"""
WEAKNESS ML TARGET LABEL MODULE

Defines deterministic baseline target labeling rules for candidate skill weakness ML dataset.
Target label formulation:
  1 = meaningful skill weakness (requires improvement)
  0 = no meaningful weakness (sufficient proficiency)

Rule:
  weakness = 1 if level_gap > 0 OR total_score < 0.60
  otherwise weakness = 0
"""

from typing import Dict, Any, Optional, Union

# Baseline threshold constant
WEAKNESS_SCORE_THRESHOLD: float = 0.60
TARGET_LABEL_KEY: str = "is_weakness"


def compute_weakness_target_label(
    feature_dict_or_gap: Union[Dict[str, Any], int, float],
    total_score: Optional[float] = None
) -> int:
    """
    Computes binary target label (1 or 0) for an assessed skill.

    Parameters:
        feature_dict_or_gap: Either a feature dictionary containing 'level_gap' and 'total_score',
                             or an integer/float representing 'level_gap'.
        total_score (float, optional): Total score ratio [0.0, 1.0] if level_gap passed directly.

    Returns:
        int: 1 for weakness, 0 for no weakness.
    """
    if isinstance(feature_dict_or_gap, dict):
        level_gap = feature_dict_or_gap.get("level_gap", 0)
        score = feature_dict_or_gap.get("total_score", 0.0)
    else:
        level_gap = feature_dict_or_gap
        score = total_score if total_score is not None else 0.0

    try:
        level_gap_val = int(level_gap) if level_gap is not None else 0
    except (ValueError, TypeError):
        level_gap_val = 0

    try:
        score_val = float(score) if score is not None else 0.0
    except (ValueError, TypeError):
        score_val = 0.0

    score_val = round(score_val, 4)

    if level_gap_val > 0 or score_val < WEAKNESS_SCORE_THRESHOLD:
        return 1
    return 0


# Convenient function aliases
compute_weakness_label = compute_weakness_target_label
compute_target_label = compute_weakness_target_label
