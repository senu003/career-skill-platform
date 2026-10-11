import os
import sys
import json
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from app.services.requirement_service import evaluate_cv_with_gemini
from app.services.skill_analysis_service import combine_cv_and_assessment
from app.ml.readiness_features import extract_model2_features
from app.ml.predict_readiness import Model2FinalRecommendationPredictor
from app.ml.predict_weakness import Model1SkillEvaluator

def main():
    case_path = Path('eval/cases/case_001.txt')
    with open(case_path, 'r', encoding='utf-8') as f:
        cv_text = f.read()
        
    print("=== EXTRACTED CV TEXT (First 300 chars) ===")
    print(cv_text[:300])
    print("=" * 40)
    
    reqs = [
        {"skill": "Python", "level": "advanced", "importance": "required"},
        {"skill": "Django", "level": "intermediate", "importance": "required"}
    ]
    
    print("\nRunning evaluate_cv_with_gemini with mock=True (fallback regex)...")
    res = evaluate_cv_with_gemini(cv_text, reqs, mock=True, refresh=True)
    
    cv_matching_result = {
        "matched_skills": [r for r in res if r['cv_match_status'] == 'Match'],
        "missing_skills": [r for r in res if r['cv_match_status'] != 'Match'],
        "skills": res,
        "score_data": {}
    }
    print("\n=== PARSED MATCHES ===")
    print(json.dumps(cv_matching_result, indent=2))
    
    assessment_for_case = {
        "Python": {"assessed_level": "basic", "total_score": 0.5},
        "Django": {"assessed_level": "basic", "total_score": 0.5}
    }
    
    combined = combine_cv_and_assessment(cv_matching_result, db_or_assessments=assessment_for_case)
    print("\n=== COMBINED RESULT ===")
    # Print a summary to save space
    for s in combined['skills']:
        print(f"Skill: {s['skill']}, cv_match: {s['cv_match_status']}, assessed: {s['assessed_level']}, gap: {s['level_gap']}")
    
    features = extract_model2_features(combined)
    print("\n=== FEATURES ===")
    print(json.dumps(features, indent=2))
    
    m2 = Model2FinalRecommendationPredictor()
    m2_res = m2.predict(features)
    print("\n=== FINAL VERDICT ===")
    print(json.dumps(m2_res, indent=2))
    
if __name__ == '__main__':
    main()
