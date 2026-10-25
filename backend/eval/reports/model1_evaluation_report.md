# MODEL1 Offline Evaluation & Benchmark Audit Report

> [!IMPORTANT]
> **Execution Timestamp**: `2026-10-25T05:36:57.249555+00:00`  
> **Model Artifact**: `E:\career-skill-platform\backend\models\model1_skill_evaluator.joblib`  
> **Artifact SHA-256**: `bd731396f4161b5ea2263328f75c0cb3e185a2c74080a66f2b05bfc718a5693b`  
> **Benchmark Version**: `1.0.0` (SHA-256: `7ef417ddfb12c8f2...`)

> [!WARNING]
> SYNTHETIC BENCHMARK NOTICE: This benchmark dataset is generated from heuristic domain simulation formulas. High performance on this benchmark verifies model consistency, algorithm fit, and schema conformance against the synthetic generation rules, but does NOT represent human-annotated ground truth or proof of real-world candidate job readiness.

---

## 1. Executive Summary & Baseline Comparison

| Metric | Production ML Artifact | Deterministic Rule Baseline | Dummy (Most Frequent) Baseline | Lift vs Dummy | Lift vs Rules |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Accuracy** | **0.9920** | 0.9380 | 0.2500 | +0.7420 | +0.0540 |
| **Balanced Accuracy** | **0.9920** | 0.9380 | 0.2500 | +0.7420 | +0.0540 |
| **Macro Precision** | **0.9920** | 0.9490 | 0.0625 | +0.9295 | +0.0430 |
| **Macro Recall** | **0.9920** | 0.9380 | 0.2500 | +0.7420 | +0.0540 |
| **Macro F1 Score** | **0.9920** | 0.9379 | 0.1000 | +0.8920 | +0.0541 |
| **Macro ROC-AUC** | **0.9983** | N/A | 0.5 | N/A | N/A |

## 2. Per-Class Performance Breakdown

| Class Label | Precision | Recall | F1 Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| `Mastered` | 0.9920 | 0.9920 | 0.9920 | 125 |
| `Re-learn Basics` | 0.9843 | 1.0000 | 0.9921 | 125 |
| `Speed Practice` | 1.0000 | 1.0000 | 1.0000 | 125 |
| `Upgrade Needed` | 0.9919 | 0.9760 | 0.9839 | 125 |

## 3. Confusion Matrix (Rows: Actual, Columns: Predicted)

| Actual \ Predicted | `Mastered` | `Re-learn Basics` | `Speed Practice` | `Upgrade Needed` |
| :--- | :---: | :---: | :---: | :---: |
| `Mastered` | 124 | 0 | 0 | 1 |
| `Re-learn Basics` | 0 | 125 | 0 | 0 |
| `Speed Practice` | 0 | 0 | 125 | 0 |
| `Upgrade Needed` | 1 | 2 | 0 | 122 |

## 4. Probability Calibration Analysis

- **Macro Brier Score**: `0.0039` (lower is better, 0.0 is perfect)
- **Per-Class Brier Scores**:
  - `Mastered`: `0.0053`
  - `Re-learn Basics`: `0.0027`
  - `Speed Practice`: `0.0001`
  - `Upgrade Needed`: `0.0075`

## 6. Audit Findings & Limitations

1. **Synthetic Constraint**: The benchmark evaluates accuracy against synthetic latent generation equations.
2. **Production Safety**: Existing `.joblib` model artifacts are untouched and verified intact.
3. **Zero Inversions**: Sanity audits confirm no catastrophic inversions (e.g., zero failures labeled Mastered).
