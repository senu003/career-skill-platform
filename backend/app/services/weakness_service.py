from typing import Dict, Any, Optional

def calculate_weakness(level_gap: Optional[int], total_score: Optional[float]) -> Dict[str, Any]:
    """
    Centralized deterministic weakness identification.
    
    is_weakness = level_gap > 0 OR total_score < 0.60
    
    Returns a dictionary with:
    - is_weakness: bool
    - weakness_reason: str ("LEVEL_GAP", "LOW_SCORE", "LEVEL_GAP_AND_LOW_SCORE", "NONE")
    """
    has_gap = level_gap is not None and level_gap > 0
    has_low_score = total_score is not None and total_score < 0.60
    
    is_weakness = has_gap or has_low_score
    
    if has_gap and has_low_score:
        reason = "LEVEL_GAP_AND_LOW_SCORE"
    elif has_gap:
        reason = "LEVEL_GAP"
    elif has_low_score:
        reason = "LOW_SCORE"
    else:
        reason = "NONE"
        
    return {
        "is_weakness": is_weakness,
        "weakness_reason": reason
    }
