def calculate_skill_score(matched_skills, missing_skills):
    """
    Calculates skill match score percentage and metadata.

    Args:
        matched_skills (list): List of matched skill items.
        missing_skills (list): List of missing skill items.

    Returns:
        dict: Dictionary containing total_skills, matched_count, missing_count, and score.
    """
    matched_count = len(matched_skills) if matched_skills is not None else 0
    missing_count = len(missing_skills) if missing_skills is not None else 0
    total_skills = matched_count + missing_count

    if total_skills == 0:
        score = 0.0
    else:
        score = round((matched_count / total_skills) * 100, 2)

    return {
        "total_skills": total_skills,
        "matched_count": matched_count,
        "missing_count": missing_count,
        "score": score
    }