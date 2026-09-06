from typing import Dict, Any, Optional

def generate_recommendation(
    skill: str, 
    required_level: Optional[str], 
    assessed_level: Optional[str], 
    level_gap: Optional[int], 
    total_score: Optional[float], 
    is_weakness: bool, 
    weakness_reason: str
) -> Dict[str, Any]:
    """
    Generate rule-based recommendations.
    
    Priority classification rules:
    - No weakness (is_weakness == False): Priority = LOW
    - Level gap == 1 (score >= 0.60): Priority = MEDIUM
    - Level gap >= 2 or Score < 0.40 or (Level gap > 0 and Score < 0.60): Priority = HIGH
    """
    if not is_weakness:
        priority = "LOW"
        reason = "Skill meets or exceeds requirements with satisfactory performance."
        recommendation = f"Continue practicing {skill} to maintain proficiency."
    else:
        # Determine priority
        is_high = False
        if level_gap is not None and level_gap >= 2:
            is_high = True
        elif total_score is not None and total_score < 0.40:
            is_high = True
        elif level_gap is not None and level_gap > 0 and total_score is not None and total_score < 0.60:
            is_high = True
            
        priority = "HIGH" if is_high else "MEDIUM"
        
        # Determine recommendation based on reason
        if weakness_reason == "LEVEL_GAP_AND_LOW_SCORE":
            reason = f"Candidate assessed at {assessed_level} but requires {required_level}, and scored poorly ({total_score:.0%} accuracy)."
            recommendation = f"Immediate foundational review of {skill} is required to reach {required_level} level."
        elif weakness_reason == "LEVEL_GAP":
            reason = f"Candidate assessed at {assessed_level} but requires {required_level}."
            recommendation = f"Targeted practice required to elevate {skill} from {assessed_level} to {required_level}."
        elif weakness_reason == "LOW_SCORE":
            reason = f"Candidate met level requirements but scored poorly ({total_score:.0%} accuracy)."
            recommendation = f"Review weak areas in {skill} to solidify knowledge and improve accuracy."
        else:
            reason = "Skill requires improvement."
            recommendation = f"Focus on improving {skill} skills."

    return {
        "priority": priority,
        "recommendation": recommendation,
        "reason": reason
    }
