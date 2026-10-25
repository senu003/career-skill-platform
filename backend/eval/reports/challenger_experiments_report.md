# Phase 3 — Stage 3: Controlled Challenger Experiments Report

> [!IMPORTANT]
> **Execution Timestamp**: `2026-10-25T05:38:09.974144+00:00`  
> **Model 1 Decision**: `NO PROMOTION RECOMMENDED`  
> **Model 2 Decision**: `NO PROMOTION RECOMMENDED`  

> [!WARNING]
> SYNTHETIC BENCHMARK NOTICE: This benchmark dataset is generated from heuristic domain simulation formulas. High performance on this benchmark verifies model consistency, algorithm fit, and schema conformance against the synthetic generation rules, but does NOT represent human-annotated ground truth or proof of real-world candidate job readiness.

---

## 1. Pre-Experiment Verification Summary

| Audit Check | Status | Verification Detail |
| :--- | :---: | :--- |
| Model 1 Champion SHA-256 | **PASS** | `bd731396f4161b5e...` |
| Model 2 Champion SHA-256 | **PASS** | `e615fa17e4fa0884...` |
| Model 1 Benchmark SHA-256 | **PASS** | `7ef417ddfb12c8f2...` |
| Model 2 Benchmark SHA-256 | **PASS** | `192ead2630e52f41...` |
| Benchmark Leakage / Overlap | **PASS** | `0` rows overlap between training datasets and benchmarks |
| Schema & Target Invariance | **PASS** | All feature names, order, types, and classes preserved |

---

## 2. Model 1: Skill Evaluator Champion vs. Challenger Comparison

### 2.1 Overall Performance Metrics on Persisted Benchmark

| Model Variant | Type | Accuracy | Balanced Acc | Macro F1 | ROC-AUC | F1 Lift vs Champion | F1 Lift vs Dummy | Size (KB) | Gate Decision |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Production Champion** | RF (d=8) | **0.9920** | **0.9920** | **0.9920** | 0.9983 | baseline | +0.8920 | 305 | **CHAMPION** |
| Deterministic Rules | Rules | 0.9380 | 0.9380 | 0.9379 | N/A | -0.0541 | +0.8379 | N/A | BASELINE |
| Dummy (Most Frequent) | Dummy | 0.2500 | 0.2500 | 0.1000 | N/A | -0.8920 | baseline | N/A | BASELINE |
| `model1_rf_v1` | random_forest | 0.9920 | 0.9920 | 0.9920 | 0.9997 | +0.0000 | +0.8920 | 451.8 | `NO PROMOTION RECOMMENDED` |
| `model1_rf_v2` | random_forest | 0.9900 | 0.9900 | 0.9900 | 0.9996 | -0.0020 | +0.8900 | 695.3 | `NO PROMOTION RECOMMENDED` |
| `model1_gb` | gradient_boosting | 0.9900 | 0.9900 | 0.9900 | 0.9976 | -0.0020 | +0.8900 | 785.2 | `NO PROMOTION RECOMMENDED` |

### 2.2 Model 1 Critical Class Performance: `Re-learn Basics`

| Candidate | Precision | Recall | F1 Score | Recall Degradation | Safety Violations |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Production Champion** | 0.9843 | 1.0000 | 0.9921 | baseline | 0 |
| `model1_rf_v1` | 0.9843 | 1.0000 | 0.9921 | +0.0000 | 0 |
| `model1_rf_v2` | 0.9843 | 1.0000 | 0.9921 | +0.0000 | 0 |
| `model1_gb` | 0.9843 | 1.0000 | 0.9921 | +0.0000 | 0 |

---

## 3. Model 2: Final Recommendation Engine Champion vs. Challenger Comparison

### 3.1 Overall Performance Metrics on Persisted Benchmark

| Model Variant | Type | Accuracy | Balanced Acc | Macro F1 | ROC-AUC | F1 Lift vs Champion | Rule Disagreement | Gate Decision |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Production Champion** | RF (d=6) | **0.8933** | **0.8939** | **0.8936** | 0.9702 | baseline | 19.67% | **CHAMPION** |
| Deterministic Rules | Rules | 0.8133 | 0.8129 | 0.8139 | N/A | -0.0797 | 0.00% | PROD VERDICT |
| Dummy (Most Frequent) | Dummy | 0.3500 | 0.3333 | 0.1728 | N/A | -0.7208 | N/A | BASELINE |
| `model2_rf_v1` | random_forest | 0.8833 | 0.8832 | 0.8833 | 0.969 | -0.0103 | 20.00% | `NO PROMOTION RECOMMENDED` |
| `model2_rf_v2` | random_forest | 0.9000 | 0.8999 | 0.8997 | 0.968 | +0.0061 | 19.00% | `NO PROMOTION RECOMMENDED` |
| `model2_rf_v3` | random_forest | 0.8900 | 0.8900 | 0.8900 | 0.9692 | -0.0036 | 20.67% | `NO PROMOTION RECOMMENDED` |
| `model2_gb` | gradient_boosting | 0.8867 | 0.8851 | 0.8854 | 0.9632 | -0.0082 | 21.00% | `NO PROMOTION RECOMMENDED` |

### 3.2 Model 2 Critical Class Performance: `Major Upskill Required` & False `Interview Ready`

| Candidate | Major Upskill Precision | Major Upskill Recall | Major Upskill F1 | False Interview Ready | Rule Disagreements |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Production Champion** | 0.9674 | 0.8725 | 0.9175 | 5 | 59 |
| `model2_rf_v1` | 0.9674 | 0.8725 | 0.9175 | 8 | 60 |
| `model2_rf_v2` | 0.9780 | 0.8725 | 0.9223 | 7 | 57 |
| `model2_rf_v3` | 0.9677 | 0.8824 | 0.9231 | 7 | 62 |
| `model2_gb` | 0.9674 | 0.8725 | 0.9175 | 11 | 63 |

---

## 4. Promotion Gate Evaluation & Detailed Criteria Audit

### 4.1 Acceptance Criteria Definitions
1. **Macro F1 Lift**: Must improve by at least `+0.0200` over the current champion.
2. **Critical-Class Recall**: Must not degrade by more than `1.0%` (<= 0.0100 degradation).
3. **Dummy Baseline Exceeded**: Candidate must exceed the dummy baseline Macro F1.
4. **Safety Checks**: Zero domain safety invariant violations.
5. **Deterministic Rule Disagreement**: Disagreement rate must not exceed approved 15% threshold or champion baseline + 2%.
6. **Contract Invariance**: Exact 12/10 feature orders, preprocessing, and output contracts unchanged.

### 4.2 Gate Decisions Breakdown

#### Model 1 (Skill Evaluator)

| Candidate | F1 Lift (Req >= +0.02) | Crit Recall Degradation (Req <= 0.01) | Safety Passed | Rule Disagreement | Decision |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `model1_rf_v1` | +0.0000 (FAIL) | +0.0000 (PASS) | PASS | N/A | **NO PROMOTION RECOMMENDED** |
| `model1_rf_v2` | -0.0020 (FAIL) | +0.0000 (PASS) | PASS | N/A | **NO PROMOTION RECOMMENDED** |
| `model1_gb` | -0.0020 (FAIL) | +0.0000 (PASS) | PASS | N/A | **NO PROMOTION RECOMMENDED** |

#### Model 2 (Final Recommendation Engine)

| Candidate | F1 Lift (Req >= +0.02) | Crit Recall Degradation (Req <= 0.01) | Safety Passed | Rule Disagreement | Decision |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `model2_rf_v1` | -0.0103 (FAIL) | +0.0000 (PASS) | PASS | 20.00% (FAIL) | **NO PROMOTION RECOMMENDED** |
| `model2_rf_v2` | +0.0061 (FAIL) | +0.0000 (PASS) | PASS | 19.00% (FAIL) | **NO PROMOTION RECOMMENDED** |
| `model2_rf_v3` | -0.0036 (FAIL) | -0.0099 (PASS) | PASS | 20.67% (FAIL) | **NO PROMOTION RECOMMENDED** |
| `model2_gb` | -0.0082 (FAIL) | +0.0000 (PASS) | PASS | 21.00% (FAIL) | **NO PROMOTION RECOMMENDED** |

---

## 5. Audit Conclusion & Next Steps

1. **No Promotion Recommended**: None of the challenger models passed every required promotion criterion. Specifically:
   - **Model 1**: Production champion achieves `0.9920` Macro F1 on the synthetic benchmark. A `+0.0200` lift is mathematically impossible (would require `1.0120`). Challenger variants achieve identical or slightly lower F1 (`0.9900` - `0.9920`).
   - **Model 2**: Production champion achieves `0.8936` Macro F1 with 19.67% rule disagreement and 5 false `Interview Ready` predictions. The highest-performing challenger (`model2_rf_v2`) achieves `0.8997` (+0.0061 lift), falling short of the required +0.0200 threshold. Furthermore, `model2_rf_v2` exhibits 19.00% rule disagreement (exceeding the approved 15.00% threshold) and increases false `Interview Ready` predictions from 5 to 7.
2. **Production Integrity Preserved**: No challenger model has been promoted. Production artifacts in `backend/models/` remain strictly untouched.
3. **Inference Unchanged**: Production Model 2 verdict generation continues to be governed by deterministic rules in `app/ml/predict_readiness.py`, with ML running only as a logged challenger.
4. **Synthetic Limitation Notice**: As established throughout Phase 3, these benchmark results reflect alignment with heuristic latent formulas and do not establish unverified real-world human hiring accuracy.
