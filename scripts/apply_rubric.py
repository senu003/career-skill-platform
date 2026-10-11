import json, csv
from pathlib import Path

def get_level_val(lvl):
    lvl = str(lvl).lower()
    if lvl == 'advanced': return 3
    if lvl == 'intermediate': return 2
    if lvl == 'basic': return 1
    return 0

def label_from_rubric(job_requirements, expected_missing_skills, assessment_profile):
    required_count = 0
    failed_count = 0
    has_critical_failure = False

    for req in job_requirements:
        imp = str(req.get('importance', '')).lower()
        if 'required' not in imp and 'critical' not in imp:
            continue
            
        required_count += 1
        skill_name = req['skill'].strip()
        req_level = req.get('level', 'unspecified')
        
        is_missing_cv = any(skill_name.lower() == ms.strip().lower() for ms in expected_missing_skills)
        # Match assessment keys case-insensitively just in case
        assessment_match = None
        for k in assessment_profile.keys():
            if k.strip().lower() == skill_name.lower():
                assessment_match = assessment_profile[k]
                break
                
        failed = False
        if is_missing_cv and not assessment_match:
            failed = True
        elif assessment_match:
            score = assessment_match.get('total_score', 0)
            assessed_level = assessment_match.get('assessed_level', 'unspecified')
            
            if score < 0.40:
                failed = True
            elif get_level_val(req_level) > 0 and get_level_val(assessed_level) > 0:
                if get_level_val(req_level) - get_level_val(assessed_level) >= 2:
                    failed = True
                
        if failed:
            failed_count += 1
            if 'critical' in imp:
                has_critical_failure = True
                
    if required_count == 0:
        return "Interview Ready"
        
    share = failed_count / required_count
    
    if share <= 0.20 and not has_critical_failure:
        return "Interview Ready"
    elif share <= 0.40:
        return "Short-Term Prep"
    else:
        return "Major Upskill Required"

if __name__ == "__main__":
    labels_file = Path('eval/labels.csv')
    assessments_file = Path('eval/assessments.json')
    
    with open(assessments_file, 'r', encoding='utf-8') as f:
        assessments_data = json.load(f)
        
    rows = []
    with open(labels_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)
            
    changed_count = 0
    for row in rows:
        case_id = row['case_id']
        job_reqs = json.loads(row['job_requirements'])
        expected_missing = [s.strip() for s in row['expected_missing'].split(',') if s.strip()]
        assessment_profile = assessments_data.get(case_id, {}).get('skills', {})
        
        old_verdict = row['expected_verdict']
        new_verdict = label_from_rubric(job_reqs, expected_missing, assessment_profile)
        
        if old_verdict != new_verdict:
            changed_count += 1
            print(f"Changed {case_id}: {old_verdict} -> {new_verdict}")
        row['expected_verdict'] = new_verdict
        
    with open(labels_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"\nTotal labels changed: {changed_count}")
