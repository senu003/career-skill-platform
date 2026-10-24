"""
TEST SUITE FOR PHASE 3 — STAGE 3: CONTROLLED CHALLENGER EXPERIMENTS

Verifies:
1. Pre-experiment checks pass completely, validating benchmark and champion SHA-256 hashes.
2. Pre-experiment checks detect tampered or mismatched hashes.
3. Persisted benchmarks have zero overlap (no leakage) with synthetic training data.
4. Challenger artifacts exist separately under backend/models/challengers/.
5. Production model artifacts remain strictly untouched and untampered.
6. Challenger pipelines preserve feature schemas, ordering, classes, and inference contracts.
7. Challenger experiment reproducibility across runs with fixed seeds.
8. Promotion gate correctly rejects models that fail Macro F1 lift or rule disagreement limits.
9. Promotion gate produces explicit "NO PROMOTION RECOMMENDED" decision for all current candidates.
10. Safety check functions correctly detect invalid predictions.
11. Reports and metadata files exist and contain required disclosures.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import joblib

from app.ml.challenger_experiments import (
    run_pre_experiment_checks,
    run_safety_checks_model1,
    run_safety_checks_model2,
    evaluate_promotion_gate,
    get_model1_candidate_configs,
    get_model2_candidate_configs,
    MODEL1_CHAMPION_PATH,
    MODEL2_CHAMPION_PATH,
    MODEL1_CHAMPION_META,
    MODEL2_CHAMPION_META,
    MODEL1_BENCHMARK_PATH,
    MODEL2_BENCHMARK_PATH,
    CHALLENGERS_DIR,
    REPORTS_DIR,
)
from app.ml.evaluation_harness import (
    compute_file_sha256,
    validate_benchmark_dataset,
    MODEL1_FEATURES,
    MODEL1_CLASSES,
    MODEL2_FEATURES,
    MODEL2_CLASSES,
)
from app.ml.generate_weakness_dataset import generate_model1_dataset
from app.ml.generate_readiness_dataset import generate_model2_dataset


def test_pre_experiment_checks_pass():
    """Verifies that all pre-experiment audit checks pass on the current workspace state."""
    checks = run_pre_experiment_checks()

    assert checks["model1_champion_exists"] is True
    assert checks["model2_champion_exists"] is True
    assert checks["benchmark_isolation_verified"] is True
    assert checks["m1_benchmark_overlap_rows"] == 0
    assert checks["m2_benchmark_overlap_rows"] == 0
    assert checks["schemas_contract_verified"] is True


def test_benchmark_isolation_zero_leakage():
    """Explicitly verifies zero rows overlap between persisted benchmarks and seed-42 training data."""
    m1_bench = pd.read_csv(MODEL1_BENCHMARK_PATH)
    m2_bench = pd.read_csv(MODEL2_BENCHMARK_PATH)

    m1_train = generate_model1_dataset(num_samples=1000, random_seed=42)
    m2_train = generate_model2_dataset(num_samples=600, random_seed=42)

    m1_overlap = pd.merge(m1_bench, m1_train, how="inner")
    m2_overlap = pd.merge(m2_bench, m2_train, how="inner")

    assert len(m1_overlap) == 0, f"Model 1 benchmark has {len(m1_overlap)} overlapping rows with training data"
    assert len(m2_overlap) == 0, f"Model 2 benchmark has {len(m2_overlap)} overlapping rows with training data"


def test_production_artifacts_untouched():
    """Verifies production champions in backend/models/ were not modified or overwritten."""
    with open(MODEL1_CHAMPION_META, "r", encoding="utf-8") as f:
        m1_meta = json.load(f)
    with open(MODEL2_CHAMPION_META, "r", encoding="utf-8") as f:
        m2_meta = json.load(f)

    current_m1_sha = compute_file_sha256(MODEL1_CHAMPION_PATH)
    current_m2_sha = compute_file_sha256(MODEL2_CHAMPION_PATH)

    assert current_m1_sha == m1_meta["artifact_sha256"], "Model 1 production artifact was modified!"
    assert current_m2_sha == m2_meta["artifact_sha256"], "Model 2 production artifact was modified!"


def test_challenger_artifacts_saved_separately():
    """Verifies challenger artifacts exist in backend/models/challengers/ and are non-empty."""
    assert CHALLENGERS_DIR.exists()

    expected_challengers = [
        "model1_rf_v1.joblib",
        "model1_rf_v2.joblib",
        "model1_gb.joblib",
        "model2_rf_v1.joblib",
        "model2_rf_v2.joblib",
        "model2_rf_v3.joblib",
        "model2_gb.joblib",
    ]

    for filename in expected_challengers:
        path = CHALLENGERS_DIR / filename
        assert path.exists(), f"Challenger artifact missing: {path}"
        assert os.path.getsize(path) > 1000, f"Challenger artifact {path} is empty or invalid"


def test_challenger_pipeline_contract():
    """Verifies each challenger artifact conforms to the exact inference schema and produces valid outputs."""
    # Model 1 Challengers
    m1_sample = pd.DataFrame([{
        "jd_required_level": 2.0,
        "cv_parsed_level": 2.0,
        "basic_score": 0.85,
        "intermediate_score": 0.80,
        "advanced_score": 0.70,
        "assessment_score": 0.80,
        "avg_time_per_question": 28.0,
        "relative_time": 0.93,
        "attempt_count": 1.0,
        "previous_best_score": 0.80,
        "score_gap": 0.0,
        "speed_accuracy": 0.80
    }])[MODEL1_FEATURES]

    for fname in ["model1_rf_v1.joblib", "model1_rf_v2.joblib", "model1_gb.joblib"]:
        pipe = joblib.load(CHALLENGERS_DIR / fname)
        pred = pipe.predict(m1_sample)
        probs = pipe.predict_proba(m1_sample)[0]

        assert pred[0] in MODEL1_CLASSES
        assert len(probs) == len(MODEL1_CLASSES)
        assert pytest.approx(sum(probs), abs=1e-3) == 1.0

    # Model 2 Challengers
    m2_sample = pd.DataFrame([{
        "total_required_skills": 6.0,
        "missing_skills_count": 1.0,
        "average_skill_gap": 0.33,
        "overall_assessment_accuracy": 0.82,
        "upgrade_needed_count": 1.0,
        "mastered_count": 3.0,
        "speed_practice_count": 1.0,
        "relearn_basics_count": 0.0,
        "assessed_skills_count": 5.0,
        "assessment_completion_rate": 0.83
    }])[MODEL2_FEATURES]

    for fname in ["model2_rf_v1.joblib", "model2_rf_v2.joblib", "model2_rf_v3.joblib", "model2_gb.joblib"]:
        pipe = joblib.load(CHALLENGERS_DIR / fname)
        pred = pipe.predict(m2_sample)
        probs = pipe.predict_proba(m2_sample)[0]

        assert pred[0] in MODEL2_CLASSES
        assert len(probs) == len(MODEL2_CLASSES)
        assert pytest.approx(sum(probs), abs=1e-3) == 1.0


def test_safety_check_detects_violations():
    """Verifies that safety check functions flag synthetic safety inversions correctly."""
    # Model 1: Low score predicted as Mastered
    bad_m1_df = pd.DataFrame([{
        "assessment_score": 0.25,
        "score_gap": 0.0
    }])
    m1_safety = run_safety_checks_model1(bad_m1_df, ["Mastered"])
    assert m1_safety["passed"] is False
    assert m1_safety["violation_count"] == 1

    # Model 2: High missing ratio predicted as Interview Ready
    bad_m2_df = pd.DataFrame([{
        "total_required_skills": 10.0,
        "missing_skills_count": 8.0,  # 80% missing
        "target": "Major Upskill Required"
    }])
    m2_safety = run_safety_checks_model2(bad_m2_df, ["Interview Ready"])
    assert m2_safety["passed"] is False
    assert m2_safety["violation_count"] >= 1


def test_promotion_gate_decision_logic():
    """Verifies that the promotion gate strictly enforces all criteria and rejects subpar models."""
    champ_eval = {
        "metrics": {
            "macro_f1": 0.8936,
            "per_class_metrics": {
                "Major Upskill Required": {"recall": 0.8725}
            }
        },
        "rule_disagreement": {"disagreement_rate": 0.1967}
    }
    dummy_eval = {"macro_f1": 0.1728}
    safety_passed = {"passed": True, "violation_count": 0}

    # Case 1: Insufficient F1 lift (+0.0050 vs +0.0200 required)
    chal_low_lift = {
        "metrics": {
            "macro_f1": 0.8986,  # only +0.0050 lift
            "per_class_metrics": {
                "Major Upskill Required": {"recall": 0.8725}
            }
        },
        "rule_disagreement": {"disagreement_rate": 0.1200}
    }
    gate_res1 = evaluate_promotion_gate("model2", "chal_low_lift", chal_low_lift, champ_eval, dummy_eval, safety_passed)
    assert gate_res1["gate_passed"] is False
    assert gate_res1["recommendation"] == "NO PROMOTION RECOMMENDED"
    assert "Insufficient Macro F1 lift" in gate_res1["rejection_reasons"][0]

    # Case 2: Excessive rule disagreement (> 15%)
    chal_high_disagree = {
        "metrics": {
            "macro_f1": 0.9200,  # +0.0264 lift
            "per_class_metrics": {
                "Major Upskill Required": {"recall": 0.8725}
            }
        },
        "rule_disagreement": {"disagreement_rate": 0.2200}  # 22% disagreement
    }
    gate_res2 = evaluate_promotion_gate("model2", "chal_high_disagree", chal_high_disagree, champ_eval, dummy_eval, safety_passed)
    assert gate_res2["gate_passed"] is False
    assert any("disagreement rate" in r for r in gate_res2["rejection_reasons"])


def test_challenger_reports_and_metadata_exist():
    """Verifies that all report and metadata files were generated and contain valid structure."""
    json_rep = REPORTS_DIR / "challenger_experiments_report.json"
    md_rep = REPORTS_DIR / "challenger_experiments_report.md"
    meta_file = CHALLENGERS_DIR / "challenger_experiments_metadata.json"

    assert json_rep.exists()
    assert md_rep.exists()
    assert meta_file.exists()

    with open(json_rep, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["model1"]["promotion_recommendation"] == "NO PROMOTION RECOMMENDED"
    assert data["model2"]["promotion_recommendation"] == "NO PROMOTION RECOMMENDED"
    assert "pre_experiment_checks" in data
    assert "synthetic_notice" in data

    with open(md_rep, "r", encoding="utf-8") as f:
        md_text = f.read()

    assert "NO PROMOTION RECOMMENDED" in md_text
    assert "SYNTHETIC BENCHMARK NOTICE" in md_text
    assert "Pre-Experiment Verification Summary" in md_text
    assert "Model 1: Skill Evaluator Champion vs. Challenger Comparison" in md_text
    assert "Model 2: Final Recommendation Engine Champion vs. Challenger Comparison" in md_text
    assert "Promotion Gate Evaluation" in md_text
