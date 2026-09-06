# Synthetic Longitudinal Dataset README

> [!IMPORTANT]
> DEVELOPMENT / EXPERIMENTAL DATA  
> NOT REAL CANDIDATE DATA  
> NOT FOR CLAIMING REAL-WORLD MODEL PERFORMANCE  

## Overview
This synthetic dataset simulates longitudinal candidate assessment progressions (`Candidate → Skill → Attempt t0 → Attempt t1`) for ML development, feature engineering, baseline validation, and pipeline testing.

## Dataset Metadata
- **Generation Seed**: 42
- **Total Rows (Longitudinal Pairs)**: 1038
- **Unique Candidates**: 250
- **Unique Skills**: 5
- **Improvement Rate (improved=1)**: 48.65% (505 / 1038)
- **Class 0 Rate (improved=0)**: 51.35% (533 / 1038)
- **Missing Values**: 0
- **Duplicate Pair Rows**: 0

## Target Definition
Strictly defined as:
```python
improved = 1 if later_total_score > previous_total_score else 0
```
- No `level_change` or arbitrary thresholds re-define the target.

## Feature Matrix (Pre-t0 Features Only)
The feature matrix consists strictly of information available at time $t0$:
1. `previous_total_score` (0.0 to 100.0)
2. `previous_assessed_level` (1=basic, 2=intermediate, 3=advanced)
3. `required_level` (1=basic, 2=intermediate, 3=advanced)
4. `previous_level_gap` (max(0, required_level - previous_assessed_level))
5. `cv_match_score` (0.0 to 100.0)
6. `previous_is_weakness` (1 if level_gap > 0 or total_score < 70 else 0)
7. `previous_priority` ("High", "Medium", "Low")
8. `days_between_attempts` (3 to 90 days)
9. `previous_basic_score` (0.0 to 100.0)
10. `previous_intermediate_score` (0.0 to 100.0)
11. `previous_advanced_score` (0.0 to 100.0)

## Data Leakage Audit
- Automated validation verifies that zero $t1$ metrics (`later_total_score`, `later_assessed_level`, etc.) exist in the feature matrix.
- `leakage_audit_passed`: True
