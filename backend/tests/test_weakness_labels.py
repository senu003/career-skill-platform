"""
TEST SUITE FOR WEAKNESS ML TARGET LABELS (Step 2)
"""

import pytest
from app.ml.weakness_labels import (
    compute_weakness_target_label,
    compute_weakness_label,
    compute_target_label,
    WEAKNESS_SCORE_THRESHOLD,
    TARGET_LABEL_KEY
)


def test_level_gap_causing_weakness():
    """Verify that level_gap > 0 causes target label = 1 regardless of score."""
    # level_gap = 1, high score 0.85 -> weakness = 1
    res = compute_weakness_target_label({"level_gap": 1, "total_score": 0.85})
    assert res == 1

    # level_gap = 2, score 0.90 -> weakness = 1
    res_direct = compute_weakness_target_label(2, 0.90)
    assert res_direct == 1


def test_score_below_threshold_causing_weakness():
    """Verify total_score < 0.60 causes target label = 1 even with level_gap = 0."""
    res = compute_weakness_target_label({"level_gap": 0, "total_score": 0.55})
    assert res == 1

    res_direct = compute_weakness_target_label(0, 0.40)
    assert res_direct == 1

    res_zero = compute_weakness_target_label({"level_gap": 0, "total_score": 0.0})
    assert res_zero == 1


def test_no_gap_and_score_above_threshold_producing_non_weakness():
    """Verify no level gap + total_score >= 0.60 produces target label = 0."""
    res = compute_weakness_target_label({"level_gap": 0, "total_score": 0.65})
    assert res == 0

    res_high = compute_weakness_target_label({"level_gap": 0, "total_score": 1.0})
    assert res_high == 0

    res_direct = compute_weakness_target_label(0, 0.75)
    assert res_direct == 0


def test_boundary_score_exactly_060():
    """Verify total_score exactly equal to 0.60 with level_gap = 0 produces label = 0."""
    res = compute_weakness_target_label({"level_gap": 0, "total_score": 0.60})
    assert res == 0

    res_direct = compute_weakness_target_label(0, 0.60)
    assert res_direct == 0


def test_missing_or_zero_assessed_level():
    """Verify unassessed (level 0) or missing assessed level resulting in gap > 0 causes weakness = 1."""
    # Required level intermediate (2), assessed level 0 -> gap = 2 -> weakness = 1
    res = compute_weakness_target_label({"level_gap": 2, "total_score": 0.80})
    assert res == 1

    # Required level basic (1), assessed level 0 -> gap = 1 -> weakness = 1
    res_gap1 = compute_weakness_target_label({"level_gap": 1, "total_score": 0.70})
    assert res_gap1 == 1


def test_invalid_and_missing_inputs_graceful_handling():
    """Verify robust handling of missing dict keys or invalid types."""
    assert compute_weakness_target_label({}) == 1  # level_gap=0, score=0.0 < 0.60 -> 1
    assert compute_weakness_target_label({"level_gap": None, "total_score": None}) == 1
    assert compute_weakness_target_label({"level_gap": "invalid", "total_score": "0.75"}) == 0
    assert compute_weakness_target_label(None) == 1


def test_function_aliases():
    """Verify aliases compute_weakness_label and compute_target_label work identically."""
    d = {"level_gap": 0, "total_score": 0.70}
    assert compute_weakness_label(d) == 0
    assert compute_target_label(d) == 0
