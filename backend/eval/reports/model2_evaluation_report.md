# MODEL2 Offline Evaluation & Benchmark Audit Report

> [!IMPORTANT]
> **Execution Timestamp**: `2026-10-24T18:24:28.649646+00:00`  
> **Model Artifact**: `E:\career-skill-platform\backend\models\model2_final_recommendation.joblib`  
> **Artifact SHA-256**: `e615fa17e4fa088421864d0440f53ec036e6ee89d1cba592ef80c8c14bd5ba2e`  
> **Benchmark Version**: `1.0.0` (SHA-256: `192ead2630e52f41...`)

> [!WARNING]
> SYNTHETIC BENCHMARK NOTICE: This benchmark dataset is generated from heuristic domain simulation formulas. High performance on this benchmark verifies model consistency, algorithm fit, and schema conformance against the synthetic generation rules, but does NOT represent human-annotated ground truth or proof of real-world candidate job readiness.

---

## 1. Executive Summary & Baseline Comparison

| Metric | Production ML Artifact | Deterministic Rule Baseline | Dummy (Most Frequent) Baseline | Lift vs Dummy | Lift vs Rules |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Accuracy** | **0.8933** | 0.8133 | 0.3500 | +0.5433 | +0.0800 |
| **Balanced Accuracy** | **0.8939** | 0.8129 | 0.3333 | +0.5606 | +0.0810 |
| **Macro Precision** | **0.8989** | 0.8263 | 0.1167 | +0.7822 | +0.0726 |
| **Macro Recall** | **0.8939** | 0.8129 | 0.3333 | +0.5606 | +0.0810 |
| **Macro F1 Score** | **0.8936** | 0.8139 | 0.1728 | +0.7208 | +0.0797 |
| **Macro ROC-AUC** | **0.9702** | N/A | 0.5 | N/A | N/A |

## 2. Per-Class Performance Breakdown

| Class Label | Precision | Recall | F1 Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Interview Ready` | 0.9495 | 0.8952 | 0.9216 | 105 |
| `Major Upskill Required` | 0.9674 | 0.8725 | 0.9175 | 102 |
| `Short-Term Prep` | 0.7798 | 0.9140 | 0.8416 | 93 |

## 3. Confusion Matrix (Rows: Actual, Columns: Predicted)

| Actual \ Predicted | `Interview Ready` | `Major Upskill Required` | `Short-Term Prep` |
| :--- | :---: | :---: | :---: |
| `Interview Ready` | 94 | 0 | 11 |
| `Major Upskill Required` | 0 | 89 | 13 |
| `Short-Term Prep` | 5 | 3 | 85 |

## 4. Probability Calibration Analysis

- **Macro Brier Score**: `0.0555` (lower is better, 0.0 is perfect)
- **Per-Class Brier Scores**:
  - `Interview Ready`: `0.0435`
  - `Major Upskill Required`: `0.0411`
  - `Short-Term Prep`: `0.0820`

## 5. Model 2 Challenger vs. Deterministic Rules Disagreement Analysis

- **Total Benchmark Samples**: `300`
- **Total Disagreements**: `59` (`19.67%`)

> [!NOTE]
> CRITICAL: In production, deterministic rules govern the final verdict. The Random Forest operates as a logged challenger. Disagreements do NOT alter production verdicts unless the ML model is explicitly verified and promoted.

### Cross-Tabulation Matrix (Rows: Deterministic Rules, Columns: Random Forest)

| Rules \ ML Challenger | `Interview Ready` | `Major Upskill Required` | `Short-Term Prep` |
| :--- | :---: | :---: | :---: |
| `Interview Ready` | 78 | 0 | 5 |
| `Major Upskill Required` | 1 | 83 | 24 |
| `Short-Term Prep` | 20 | 9 | 80 |

## 6. Audit Findings & Limitations

1. **Synthetic Constraint**: The benchmark evaluates accuracy against synthetic latent generation equations.
2. **Production Safety**: Existing `.joblib` model artifacts are untouched and verified intact.
3. **Zero Inversions**: Sanity audits confirm no catastrophic inversions (e.g., zero failures labeled Mastered).
