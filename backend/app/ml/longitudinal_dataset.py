import pandas as pd
from sqlalchemy.orm import Session
from app.models import User
from app.services.longitudinal_service import get_candidate_history

def build_longitudinal_dataset(db: Session) -> pd.DataFrame:
    """
    Builds a longitudinal dataset from genuine candidate history.
    Excludes guest attempts (where user_id is None).
    Creates pairs of consecutive assessments for the same candidate and skill.
    """
    # Get all genuine users
    users = db.query(User).all()
    
    records = []
    
    for user in users:
        history_by_skill = get_candidate_history(db, user.id)
        
        for skill, history in history_by_skill.items():
            # Need at least 2 attempts to form a pair
            if len(history) < 2:
                continue
                
            # Chronological ordering is already guaranteed by get_candidate_history
            for i in range(1, len(history)):
                t0 = history[i-1]
                t1 = history[i]
                
                # Check if total scores exist
                if t1["total_score"] is None or t0["total_score"] is None:
                    continue
                    
                # We specifically enforce the target as requested:
                # improved = later_total_score > previous_total_score
                target_improved = t1["total_score"] > t0["total_score"]
                
                # Using the longitudinal service's outcome dict for delta fields
                outcome = t1.get("outcome", {})
                
                records.append({
                    "user_id": user.id,
                    "skill": skill,
                    # t0 fields
                    "previous_attempt_id": t0["attempt_id"],
                    "previous_required_level": t0["required_level"],
                    "previous_assessed_level": t0["assessed_level"],
                    "previous_basic_score": t0["basic_score"],
                    "previous_intermediate_score": t0["intermediate_score"],
                    "previous_advanced_score": t0["advanced_score"],
                    "previous_total_score": t0["total_score"],
                    "previous_level_gap": t0["level_gap"],
                    "previous_is_weakness": t0["is_weakness"],
                    "previous_priority": t0["priority"],
                    "previous_completed_at": t0["completed_at"],
                    
                    # Target and outcome fields
                    "improved": target_improved,
                    "score_change": outcome.get("score_change"),
                    "level_change": outcome.get("level_change"),
                    "declined": outcome.get("declined"),
                    "persistent_weakness": outcome.get("persistent_weakness"),
                    
                    # Reference fields (NOT to be used as features)
                    "later_attempt_id": t1["attempt_id"],
                    "later_completed_at": t1["completed_at"],
                })
                
    # Return empty DataFrame with correct columns if no records
    if not records:
        return pd.DataFrame(columns=[
            "user_id", "skill", "previous_attempt_id", "previous_required_level", 
            "previous_assessed_level", "previous_basic_score", "previous_intermediate_score", 
            "previous_advanced_score", "previous_total_score", "previous_level_gap", 
            "previous_is_weakness", "previous_priority", "previous_completed_at", 
            "improved", "score_change", "level_change", "declined", "persistent_weakness", 
            "later_attempt_id", "later_completed_at"
        ])
        
    return pd.DataFrame(records)
