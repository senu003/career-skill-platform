import os
import sys
import csv
import json
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from app.services.requirement_service import evaluate_cv_with_gemini
from app.services.skill_analysis_service import combine_cv_and_assessment
from app.ml.predict_readiness import Model2FinalRecommendationPredictor
from app.ml.predict_weakness import Model1SkillEvaluator
from app.ml.predict import SkillLevelPredictor
from app.ml.readiness_features import extract_model2_features

def main():
    labels_file = Path('eval/labels.csv')
    assessments_file = Path('eval/assessments.json')
    if not labels_file.exists():
        print("eval/labels.csv not found")
        return

    cases = []
    with open(labels_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
            
    assessments_data = {}
    if assessments_file.exists():
        with open(assessments_file, 'r', encoding='utf-8') as f:
            assessments_data = json.load(f)

    true_pos = 0
    false_pos = 0
    false_neg = 0
    
    level_correct = 0
    level_total = 0
    
    model2_correct_rules = 0
    model2_correct_ml = 0
    
    rules_cm = {"Interview Ready": 0, "Short-Term Prep": 0, "Major Upskill Required": 0}
    ml_cm = {"Interview Ready": 0, "Short-Term Prep": 0, "Major Upskill Required": 0}

    total_cases = 0
    errored_cases = 0

    m1_evaluator = Model1SkillEvaluator()
    m2_predictor = Model2FinalRecommendationPredictor()
    lvl_predictor = SkillLevelPredictor()

    m1_overrides = 0
    m2_overrides = 0
    lvl_overrides = 0
    total_skills_evaluated = 0

    print("Evaluating cases...")
    for case in cases:
        case_id = case['case_id']
        case_path = Path(f'eval/cases/{case_id}.txt')
        if not case_path.exists():
            continue
            
        with open(case_path, 'r', encoding='utf-8') as f:
            cv_text = f.read()

        reqs = json.loads(case['job_requirements'])
        expected_matched = [s.strip().lower() for s in case.get('expected_matched', '').split(',') if s.strip()]
        expected_missing = [s.strip().lower() for s in case.get('expected_missing', '').split(',') if s.strip()]
        expected_verdict = case.get('expected_verdict', '').strip()

        # Gemini Matching
        try:
            gemini_results = evaluate_cv_with_gemini(cv_text, reqs, mock=False, refresh=False)
        except Exception as e:
            if "GeminiQuotaError" in str(type(e).__name__) or "GeminiQuotaError" in str(e):
                errored_cases += 1
                continue
            else:
                errored_cases += 1
                continue
        
        matched_from_gemini = []
        missing_from_gemini = []
        for res in gemini_results:
            skill_lower = res['skill'].lower()
            if res['cv_match_status'] in ['Match', 'Needs Improvement']:
                res['matched'] = True
                matched_from_gemini.append(res)
                
                if skill_lower in expected_matched:
                    true_pos += 1
                elif skill_lower in expected_missing:
                    false_pos += 1
            else:
                res['matched'] = False
                missing_from_gemini.append(res)
                
                if skill_lower in expected_matched:
                    false_neg += 1

            if res['cv_level'] not in ['not_found', 'unspecified']:
                level_total += 1
                level_correct += 1

        cv_matching_result = {
            "matched_skills": matched_from_gemini,
            "missing_skills": missing_from_gemini,
            "skills": gemini_results,
            "score_data": {}
        }
        
        assessment_for_case = assessments_data.get(case_id, {}).get("skills", {})
        
        combined_result = combine_cv_and_assessment(cv_matching_result, db_or_assessments=assessment_for_case, user_id=None)
        
        # Model 2
        m2_res = m2_predictor.predict(combined_result)
        
        rules_verdict = m2_res.get('rules_verdict')
        ml_verdict = m2_res.get('ml_verdict')
        
        if expected_verdict:
            total_cases += 1
            if total_cases == 1:
                print(f"{'ID':<10} | {'Label':<25} | {'Rules Verdict':<25} | {'ML Verdict':<25}")
                print("-" * 95)
            print(f"{case_id:<10} | {expected_verdict:<25} | {rules_verdict:<25} | {ml_verdict:<25}")
            
            if rules_verdict == expected_verdict:
                model2_correct_rules += 1
                rules_cm[rules_verdict] = rules_cm.get(rules_verdict, 0) + 1
                
            if ml_verdict and ml_verdict == expected_verdict:
                model2_correct_ml += 1
                ml_cm[ml_verdict] = ml_cm.get(ml_verdict, 0) + 1
                
            if m2_res.get('ml_override_attempted'):
                m2_overrides += 1
        
        # Checking ML predictors override
        for skill_item in combined_result['skills']:
            total_skills_evaluated += 1
            
            s_name = skill_item.get('skill', '')
            ass_data = assessment_for_case.get(s_name, {})
            has_ass = bool(ass_data)
            
            s_feats = {
                "cv_matched": 1 if skill_item.get('matched') else 0,
                "required_level": skill_item.get('required_level', 'basic'),
                "importance": skill_item.get('importance', 'required'),
                "basic_score": skill_item.get('total_score', 0.0) or 0.0,
                "intermediate_score": 0.0,
                "advanced_score": 0.0,
                "total_score": skill_item.get('total_score', 0.0) or 0.0
            }
            try:
                if has_ass:
                    lvl_res = lvl_predictor.predict_single(s_feats)
                    if lvl_res.get('ml_override_attempted'):
                        lvl_overrides += 1
            except:
                pass
                
            try:
                m1_input = {
                    "jd_required_level": skill_item.get('required_level', 'basic'),
                    "cv_parsed_level": skill_item.get('cv_level', 'not_found'),
                    "assessed_level": skill_item.get('assessed_level'),
                    "basic_score": 0.0,
                    "intermediate_score": 0.0,
                    "advanced_score": 0.0,
                    "assessment_score": skill_item.get('total_score', 0.0) or 0.0,
                    "avg_time_per_question": 30.0,
                    "attempt_count": 1,
                    "previous_best_score": skill_item.get('total_score', 0.0) or 0.0
                }
                if has_ass:
                    m1_res = m1_evaluator.predict_single(m1_input)
                    if m1_res.get('ml_override_attempted'):
                        m1_overrides += 1
            except:
                pass
                
        # Simple rate limiter (e.g. 10 requests per minute)
        import time
        # time.sleep(60.0 / 10.0) # disabled because we use mock=1
                
    # Parse Failure Rate
    parse_failures = 0.0
    pf_file = Path('eval/parse_failures.txt')
    if pf_file.exists():
        with open(pf_file, 'r') as f:
            parse_failures = float(f.read().strip())

    error_rate = errored_cases / max(1, len(cases))
    if error_rate > 0.05:
        print(f"FAILED: Error rate {error_rate*100:.1f}% exceeds 5% threshold.")
        sys.exit(1)

    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    rules_acc = model2_correct_rules / max(1, total_cases)
    ml_acc = model2_correct_ml / max(1, total_cases)
    
    output = f"""# Evaluation Results
    
*(Note: The CV texts and assessment profiles used in this evaluation are purely synthetic.)*

## 1. Skill Matching (Gemini vs Deterministic Keywords)
- **Precision**: {precision:.3f}
- **Recall**: {recall:.3f}
- **F1 Score**: {f1:.3f}
*(Note: Recall/Precision evaluated on auto-generated expected match/missing from text grep)*

## 2. Parse Failure Rate
- **Parse Failures**: {parse_failures * 100:.1f}%

## 3. Verdict Accuracy (Rules vs ML vs Rules+ML)
- **Rules Accuracy**: {rules_acc * 100:.1f}% ({model2_correct_rules}/{total_cases})
- **ML Accuracy**: {ml_acc * 100:.1f}% ({model2_correct_ml}/{total_cases})

### Confusion Matrix (Rules)
- Interview Ready: {rules_cm.get('Interview Ready', 0)} Correct
- Short-Term Prep: {rules_cm.get('Short-Term Prep', 0)} Correct
- Major Upskill Required: {rules_cm.get('Major Upskill Required', 0)} Correct

### Confusion Matrix (ML)
- Interview Ready: {ml_cm.get('Interview Ready', 0)} Correct
- Short-Term Prep: {ml_cm.get('Short-Term Prep', 0)} Correct
- Major Upskill Required: {ml_cm.get('Major Upskill Required', 0)} Correct

## 4. Override Rates
- **Model 2 Override Rate**: {m2_overrides} / {total_cases} ({(m2_overrides/max(1, total_cases))*100:.1f}%)
- **Model 1 Override Rate**: {m1_overrides} / {max(1, total_skills_evaluated)} ({(m1_overrides/max(1, total_skills_evaluated))*100:.1f}%)
- **Skill Level Override Rate**: {lvl_overrides} / {max(1, total_skills_evaluated)} ({(lvl_overrides/max(1, total_skills_evaluated))*100:.1f}%)

## 5. API Errors
- **Errored Cases**: {errored_cases} / {len(cases)} ({error_rate*100:.1f}%)
"""

    print(output)
    
    os.makedirs('eval/results', exist_ok=True)
    with open('eval/results/latest.md', 'w', encoding='utf-8') as f:
        f.write(output)

if __name__ == '__main__':
    main()
