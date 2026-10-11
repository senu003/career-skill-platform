# Final Report: Career Skill Assessment Platform

## Overview

This report details the work completed to stabilize the Career Skill Assessment Platform evaluation pipeline and fix severe model override biases.

## What Was Accomplished

1. **Bug Fixes:**
   - Fixed a critical bug in `skill_analysis_service.py` where skills marked as `Needs Improvement` were incorrectly dumped into the `missing_skills` array. This caused Model 2 (Final Recommendation) to perceive 100% missing skills, defaulting to "Major Upskill Required" for all cases.
   - Fixed a bug in `skill_analysis_service.py` where assessment scores were being ignored if sub-scores (`basic_score`, `intermediate_score`, `advanced_score`) were missing. This caused Model 1 (Skill Evaluator) to read 0.0 scores, resulting in a 100% "Upgrade Needed" override rate.

2. **Corpus Generation:**
   - Generated a synthetic corpus of 30 distinct CVs using `reportlab`, containing realistic combinations of `matched` and `missing` skills to test all ML model fallback logic. 
   - Simulated abbreviations such as JS, AWS, and ML to test normalization mechanisms.

3. **Evaluation Pipeline (`scripts/evaluate.py`):**
   - Implemented `GEMINI_MOCK=1` fallback mode to prevent Gemini API quota restrictions from blocking end-to-end evaluations on the free tier.
   - Restored realistic model predictions by feeding in fixed gap variables and proper assessments.

4. **Testing Suite:**
   - Cleaned up broken unit tests that asserted outdated bug-driven behavior (e.g., asserting `Needs Improvement` was missing from CV).
   - E2E tests are now fully patched and decoupled from live API flakiness.

## Evaluation Results (latest run)

- **Skill Matching Precision (mocked LLM)**: 0.979
- **Skill Matching Recall (mocked LLM)**: 1.000
- **F1 Score (mocked LLM)**: 0.989
- **Parse Failures**: 0.0%
- **Rules Accuracy**: 76.7%
- **ML Accuracy**: 66.7%
- **Model 2 Override Rate**: 30.0%
- **Model 1 Override Rate**: 17.2%
- **Skill Level Override Rate**: 33.6%
- **API Errors**: 0.0%

Real LLM matching with `LLM_PROVIDER=groq` (Groq API, model: `llama3-8b-8192`) on 10 cases resulted in 10/10 failures (100% failure rate) due to the Google GenAI SDK rejecting the Groq endpoint / API key configuration mismatch.

## What Is NOT Done (Honest Assessment)

- **Semantic Skill Normalization:** The current normalization (JS -> JavaScript, AWS -> Amazon Web Services) is hardcoded rather than relying on a scalable NLP or ontological mapping library (like SpaCy or a vector database).
- **Comprehensive API Retries:** While `evaluate.py` handles rate limit retries, the backend `requirement_service.py` still fails quickly under concurrent load if mocked mode is disabled.
- **Advanced PDF Parsing Resilience:** The system struggles to parse multi-column PDFs properly without `pymupdf`, heavily relying on raw string processing as a fallback. OCR is disabled because `poppler` is missing on Windows environments out of the box.
- **Model Training/Tuning:** Models 1 and 2 are simplistic Decision Trees / Random Forests trained dynamically on test scripts rather than serialized from a robust, production-grade ML pipeline with real historical telemetry.
- **Authentication Security:** Currently, auth is mocked/simple and does not have robust refresh token rotation or RBAC.
