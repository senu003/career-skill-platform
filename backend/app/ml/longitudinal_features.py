import pandas as pd

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts strictly pre-t1 features to prevent leakage.
    No t1 scores, t1 assessed levels, or t1 answers are included.
    """
    if df.empty:
        return pd.DataFrame()
        
    features = pd.DataFrame()
    
    # Base identifiers (useful for grouping, not for training directly)
    features["user_id"] = df["user_id"]
    features["skill"] = df["skill"]
    
    # t0 numerical features
    features["previous_total_score"] = df["previous_total_score"].astype(float)
    features["previous_basic_score"] = df["previous_basic_score"].astype(float)
    features["previous_intermediate_score"] = df["previous_intermediate_score"].astype(float)
    features["previous_advanced_score"] = df["previous_advanced_score"].astype(float)
    
    # Categorical/ordinal t0 features
    features["previous_required_level"] = df["previous_required_level"]
    features["previous_assessed_level"] = df["previous_assessed_level"]
    features["previous_level_gap"] = df["previous_level_gap"]
    
    # Boolean mapping
    features["previous_is_weakness"] = df["previous_is_weakness"].fillna(False).astype(int)
    
    # Time delta
    if "previous_completed_at" in df.columns and "later_completed_at" in df.columns:
        t0_time = pd.to_datetime(df["previous_completed_at"])
        t1_time = pd.to_datetime(df["later_completed_at"])
        
        # Calculate interval in days
        features["days_since_previous"] = (t1_time - t0_time).dt.total_seconds() / (24 * 3600)
        # Handle possible NaNs if dates were missing
        features["days_since_previous"] = features["days_since_previous"].fillna(0.0)
    else:
        features["days_since_previous"] = 0.0

    # Leakage check: Explicitly fail if any t1 metric leaks in
    forbidden_substrings = ["later_score", "later_level", "later_weakness", "t1_", "outcome", "improved"]
    for col in features.columns:
        for forbidden in forbidden_substrings:
            if forbidden in col.lower():
                raise ValueError(f"Leakage detected: Feature '{col}' contains future information ('{forbidden}').")
                
    return features
