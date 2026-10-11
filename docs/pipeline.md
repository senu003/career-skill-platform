# Career Skill Platform: Full Processing Pipeline

This document outlines the exact sequence of events that occurs when a candidate uploads a CV to the system, detailing how it interacts with job requirements, historical assessments, machine learning models, and deterministic scoring to generate the final evaluation.

---

## 1. CV Upload & Parsing (API: `/cv/analyze`)
* **Input**: The user uploads a PDF format CV and provides a list of job skill requirements (e.g., Python, SQL, Communication) along with the required proficiency level (Basic, Intermediate, Advanced) and importance.
* **Processing**: 
    * The system extracts raw text from the uploaded PDF using a built-in parser.
    * It validates the JSON payload containing the skill requirements.

## 2. LLM-Based Skill Matching (Gemini Service)
* **LLM Evaluation**: The extracted CV text and the parsed job requirements are passed to a Gemini LLM prompt (`evaluate_cv_with_gemini`).
* **Output generation**: For each required skill, the LLM determines if it exists in the CV (`cv_match_status`: "Match" or "Missing"). It also estimates the candidate's level (`cv_level`) based *only* on the evidence in the resume text and extracts snippets of evidence to back up its claim.

## 3. Core Database Persistence
* **State Saving**: The system saves the parsed `CV` record, a `Job` record (containing the requirements), and an `Analysis` session record for the logged-in candidate. This establishes a snapshot in time for the evaluation.

## 4. Assessment Integration
* **Historical Lookup**: The system queries the database to see if the candidate has ever taken a technical assessment for any of the required skills.
* **Score Extraction**: If an assessment exists, it extracts the `assessed_level` (Basic, Intermediate, Advanced) and calculates granular scores based on their quiz performance (`basic_score`, `intermediate_score`, `advanced_score`, and an overarching `total_score`).

## 5. Proficiency & Weakness Evaluation Pipeline
This is the most complex stage, combining multiple heuristic and ML approaches:
* **Deterministic Weakness (Rule-Based)**: The system calculates a `level_gap` (Required Level minus Assessed Level). If the candidate's assessed level is lower than required, or if their `total_score` falls below a set threshold, the skill is deterministically flagged as a weakness (`is_weakness=True`).
* **ML Skill Level Predictor**: An ML model (`SkillLevelPredictor`) attempts to predict the candidate's true proficiency level by factoring in the boolean CV match, the required level, and the candidate's granular assessment scores.
* **Model 1 (Skill Evaluator)**: A dedicated ML model generates a `skill_recommendation` (e.g., "Review Basics") and a `recommendation_confidence` score based on assessment times, previous attempt counts, and score gaps.
* **Longitudinal Improvement Tracker**: The system estimates an `improvement_probability` by looking at the candidate's historical attempts at the same skill, checking if they are likely to improve based on past trajectories.

## 6. Final Recommendation Output (Model 2: Readiness Evaluator)
* **Aggregation**: All data points (CV matching scores, assessment gaps, Model 1 outputs, missing skill counts) are bundled together.
* **Model 2 Execution**: The data is fed into **Model 2** (`Model2FinalRecommendationPredictor`).
* **Output Generation**:
    * **Final Verdict**: The model classifies the candidate into one of three categories: `"Interview Ready"`, `"Short-Term Prep"`, or `"Major Upskill Required"`.
    * **Confidence Score**: The model assigns a statistical confidence score to this verdict.
    * **Deterministic Safety Layer**: To prevent ML hallucinations or edge-case failures, the verdict passes through a hardcoded safety layer (e.g., *if 75% of skills are missing, the verdict is forced to "Major Upskill Required" regardless of what the ML predicted*).
    * **Priority Ranking**: The model outputs a ranked list of the top 5 priority skills the candidate needs to focus on to improve their employability.

---

### Summary of System Status for Evaluation
The current architecture is highly robust, utilizing a **hybrid approach**. It relies on **LLMs (Gemini)** for unstructured text extraction (CV parsing), **Deterministic Rules** for baseline safety and indisputable math (level gaps), and **Traditional ML Pipelines** (Scikit-Learn/Joblib) for nuanced predictive evaluations (Model 1 and Model 2). Current ongoing work (like `target_redesign_analysis.py`) seems focused on analyzing whether the database has enough longitudinal data to train more complex predictive models to replace some of the deterministic heuristics.
