from typing import List, Dict, Any, Optional
from app.schemas.skill_analysis import FinalSkillItemSchema
from app.schemas.aggregation import FinalAssessmentAggregationSchema, PrioritySummarySchema

def aggregate_final_assessment(skills: List[FinalSkillItemSchema]) -> FinalAssessmentAggregationSchema:
    """
    Aggregates multiple individual skill assessment results into one final candidate-level result.
    Applies importance weighting (required=1.0, preferred=0.5) to the overall score.
    """
    total_skills = len(skills)
    skills_meeting_requirement = 0
    skills_below_requirement = 0
    weakness_count = 0
    
    priority_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    
    weighted_score_sum = 0.0
    weight_total = 0.0
    
    scored_skills = []
    
    req_total = 0
    req_met = 0
    pref_total = 0
    pref_met = 0
    
    has_high_priority_required_weakness = False
    
    for s in skills:
        importance = s.importance.strip().lower()
        is_req = (importance == "required")
        
        if is_req:
            req_total += 1
        elif importance == "preferred":
            pref_total += 1
            
        # Determine if requirement is met
        # Requirement is met if assessed and level gap is 0, OR ml predicted level meets requirement
        meets = False
        if s.level_gap is not None and s.level_gap == 0:
            meets = True
        elif s.level_gap is None and s.assessed_level is None:
            # If not assessed, it's not meeting requirement deterministically 
            # We could use ml_predicted_level, but the prompt says: combining all assessed skills.
            pass
            
        if meets:
            skills_meeting_requirement += 1
            if is_req:
                req_met += 1
            elif importance == "preferred":
                pref_met += 1
        else:
            if s.assessed_level is not None or s.level_gap is not None:
                skills_below_requirement += 1
            
        if s.is_weakness:
            weakness_count += 1
            if s.priority in priority_counts:
                priority_counts[s.priority] += 1
            
            if is_req and s.priority == "HIGH":
                has_high_priority_required_weakness = True
                
        if s.total_score is not None:
            scored_skills.append((s.skill, s.total_score))
            weight = 1.0 if is_req else 0.5
            weighted_score_sum += (s.total_score * weight)
            weight_total += weight
            
    # Calculate Overall Score
    overall_score = None
    if weight_total > 0:
        overall_score = round(weighted_score_sum / weight_total, 4)
        
    # Sort strongest/weakest
    scored_skills.sort(key=lambda x: x[1], reverse=True)
    strongest_skills = [x[0] for x in scored_skills[:3]]
    
    scored_skills.sort(key=lambda x: x[1])
    weakest_skills = [x[0] for x in scored_skills[:3]]
    
    # Summaries
    req_summary = f"{req_met}/{req_total} required skills met" if req_total > 0 else "No required skills"
    pref_summary = f"{pref_met}/{pref_total} preferred skills met" if pref_total > 0 else "No preferred skills"
    
    # Readiness Status
    assessed_count = len([s for s in skills if s.assessed_level is not None or s.total_score is not None])
    
    if assessed_count == 0:
        readiness_status = "Insufficient Data"
    elif skills_meeting_requirement == assessed_count:
        readiness_status = "Excellent"
    elif has_high_priority_required_weakness or (skills_below_requirement > (assessed_count / 2)):
        readiness_status = "Needs Improvement"
    else:
        readiness_status = "Good"

    # Model 2 Predictor call for dynamic candidate readiness verdict
    final_verdict = None
    recommendation_confidence = None
    try:
        from app.ml.predict_readiness import predict_final_recommendation
        payload_dict = {
            "skills": [s.model_dump() for s in skills]
        }
        m2_res = predict_final_recommendation(payload_dict)
        final_verdict = m2_res.get("final_verdict")
        recommendation_confidence = m2_res.get("confidence")
    except Exception:
        pass

    # Aggregated ML Improvement Probability (Mean of skills with valid longitudinal history)
    valid_ml_probs = [s.improvement_probability for s in skills if s.improvement_probability is not None]
    overall_improvement_probability = (
        round(sum(valid_ml_probs) / len(valid_ml_probs), 4) if valid_ml_probs else None
    )

    return FinalAssessmentAggregationSchema(
        overall_score=overall_score,
        total_skills=total_skills,
        skills_meeting_requirement=skills_meeting_requirement,
        skills_below_requirement=skills_below_requirement,
        weakness_count=weakness_count,
        priority_summary=PrioritySummarySchema(
            high=priority_counts["HIGH"],
            medium=priority_counts["MEDIUM"],
            low=priority_counts["LOW"]
        ),
        strongest_skills=strongest_skills,
        weakest_skills=weakest_skills,
        required_skills_summary=req_summary,
        preferred_skills_summary=pref_summary,
        readiness_status=readiness_status,
        final_verdict=final_verdict,
        recommendation_confidence=recommendation_confidence,
        overall_improvement_probability=overall_improvement_probability,
        skills=skills
    )
