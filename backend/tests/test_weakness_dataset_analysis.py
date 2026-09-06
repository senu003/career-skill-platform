"""
TEST SUITE FOR WEAKNESS ML DATASET ANALYSIS MODULE

Verifies quality statistics, missing value detection, duplicate detection,
constant feature detection, explicit target leakage identification,
numeric range calculations, empty dataset handling, and non-mutation of input data.
"""

import copy
import math
import pytest
import pandas as pd

from app.ml.weakness_dataset import build_weakness_dataset, FEATURE_KEYS
from app.ml.weakness_dataset_analysis import (
    analyze_weakness_dataset,
    detect_target_leakage,
    print_weakness_dataset_report,
    PRIMARY_LEAKAGE_FEATURES,
)


def sample_attempt_1():
    return {
        "skill": "Python",
        "required_level": "intermediate",
        "assessed_level": "basic",
        "answers": [
            {"is_correct": True, "level": "basic", "answered_at": "2026-08-30T10:00:00Z"},
            {"is_correct": False, "level": "basic", "answered_at": "2026-08-30T10:00:10Z"},
        ]
    }


def sample_attempt_2():
    return {
        "skill": "SQL",
        "required_level": "basic",
        "assessed_level": "basic",
        "total_score": 0.90,
        "questions_answered_count": 5,
        "answers": [
            {"is_correct": True, "level": "basic", "answered_at": "2026-08-30T10:00:00Z"},
            {"is_correct": True, "level": "basic", "answered_at": "2026-08-30T10:00:15Z"},
        ]
    }


def test_correct_row_count_and_unique_skills():
    attempts = [sample_attempt_1(), sample_attempt_2()]
    dataset = build_weakness_dataset(attempts)
    
    report = analyze_weakness_dataset(dataset)

    assert report["row_count"] == 2
    assert report["unique_skill_count"] == 2


def test_correct_class_counts_and_weakness_percentage():
    # Attempt 1: required intermediate (2), assessed basic (1) -> gap = 1 -> is_weakness = 1
    # Attempt 2: required basic (1), assessed basic (1) -> gap = 0, score 0.90 -> is_weakness = 0
    attempts = [sample_attempt_1(), sample_attempt_2()]
    dataset = build_weakness_dataset(attempts)

    report = analyze_weakness_dataset(dataset)

    assert report["class_distribution"]["weakness"] == 1
    assert report["class_distribution"]["non_weakness"] == 1
    assert report["weakness_percentage"] == 50.0
    assert report["class_balance_ratio"] == 1.0


def test_empty_dataset_handling():
    empty_list_report = analyze_weakness_dataset([])
    assert empty_list_report["row_count"] == 0
    assert empty_list_report["unique_skill_count"] == 0
    assert empty_list_report["class_distribution"] == {"weakness": 0, "non_weakness": 0}
    assert empty_list_report["weakness_percentage"] == 0.0
    assert empty_list_report["dataset_sufficiency"]["is_sufficient_for_ml"] is False

    empty_df_report = analyze_weakness_dataset(pd.DataFrame())
    assert empty_df_report["row_count"] == 0


def test_missing_value_detection():
    # Create dataset records with explicit missing/None values
    record_with_missing = {
        "skill": "Docker",
        "required_level": 2,
        "assessed_level": None,  # Missing
        "level_gap": 2,
        "total_score": None,     # Missing
        "basic_score": 0.50,
        "is_weakness": 1,
    }
    dataset = [record_with_missing]

    report = analyze_weakness_dataset(dataset)

    assert report["missing_values"]["assessed_level"] == 1
    assert report["missing_values"]["total_score"] == 1
    assert report["missing_values"]["basic_score"] == 0


def test_duplicate_rows_and_feature_vectors():
    rec = {
        "skill": "Python",
        "required_level": 2,
        "assessed_level": 2,
        "level_gap": 0,
        "total_score": 0.80,
        "is_weakness": 0,
    }
    # 2 exact duplicates, 1 feature duplicate with different skill
    rec_diff_skill = rec.copy()
    rec_diff_skill["skill"] = "Java"

    dataset = [rec.copy(), rec.copy(), rec_diff_skill]

    report = analyze_weakness_dataset(dataset)

    assert report["row_count"] == 3
    assert report["duplicate_rows"] == 1  # 2 rec copies are exact duplicate
    assert report["duplicate_feature_rows"] == 2  # all 3 have identical features


def test_constant_feature_detection():
    # Dataset where 'required_level' is constant (1) across all rows
    rec1 = {"skill": "Python", "required_level": 1, "assessed_level": 1, "level_gap": 0, "total_score": 0.80, "is_weakness": 0}
    rec2 = {"skill": "SQL", "required_level": 1, "assessed_level": 2, "level_gap": 0, "total_score": 0.90, "is_weakness": 0}

    dataset = [rec1, rec2]

    report = analyze_weakness_dataset(dataset)

    assert "required_level" in report["constant_features"]
    assert "level_gap" in report["constant_features"]
    assert "total_score" not in report["constant_features"]


def test_target_leakage_identification_level_gap_and_total_score():
    attempts = [sample_attempt_1(), sample_attempt_2()]
    dataset = build_weakness_dataset(attempts)

    report = analyze_weakness_dataset(dataset)

    leakage_risks = report["target_leakage_risks"]
    assert "level_gap" in leakage_risks
    assert "total_score" in leakage_risks

    leakage_details = report["target_leakage_details"]
    assert "level_gap" in leakage_details["flagged_leakage_features"]
    assert "total_score" in leakage_details["flagged_leakage_features"]
    assert "level_gap" in leakage_details["leakage_reasons"]
    assert "total_score" in leakage_details["leakage_reasons"]


def test_numeric_range_reporting():
    rec1 = {"skill": "Python", "required_level": 1, "assessed_level": 1, "level_gap": 0, "total_score": 0.50, "is_weakness": 1}
    rec2 = {"skill": "SQL", "required_level": 2, "assessed_level": 1, "level_gap": 1, "total_score": 0.90, "is_weakness": 0}

    dataset = [rec1, rec2]
    report = analyze_weakness_dataset(dataset)

    total_score_range = report["numeric_ranges"]["total_score"]
    assert total_score_range["min"] == 0.50
    assert total_score_range["max"] == 0.90
    assert total_score_range["mean"] == 0.70
    assert total_score_range["std"] == 0.20


def test_no_mutation_of_original_dataset():
    attempts = [sample_attempt_1(), sample_attempt_2()]
    dataset = build_weakness_dataset(attempts)
    
    dataset_copy = copy.deepcopy(dataset)

    report = analyze_weakness_dataset(dataset)

    # Verify input dataset structure and values are completely untouched
    assert dataset == dataset_copy


def test_print_weakness_dataset_report():
    attempts = [sample_attempt_1(), sample_attempt_2()]
    dataset = build_weakness_dataset(attempts)

    report_str = print_weakness_dataset_report(dataset)

    assert "WEAKNESS ML DATASET ANALYSIS REPORT" in report_str
    assert "Total Rows:                2" in report_str
    assert "TARGET LEAKAGE ANALYSIS:" in report_str
    assert "level_gap" in report_str
    assert "total_score" in report_str
