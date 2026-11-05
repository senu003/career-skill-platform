from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import AssessmentAttempt, AssessmentAnswer, AssessmentQuestion
from app.services.skill_analysis_service import extract_assessment_scores, LEVEL_MAP
from app.services.matching_service import get_skill_variants

# Canonical skills supported by assessment system with their display labels
INTERVIEW_PREP_SKILLS = [
    {"key": "python", "canonical": "Python", "display_name": "Python"},
    {"key": "react", "canonical": "React", "display_name": "React"},
    {"key": "javascript", "canonical": "JavaScript", "display_name": "JavaScript"},
    {"key": "postgresql", "canonical": "PostgreSQL", "display_name": "SQL / PostgreSQL"},
    {"key": "docker", "canonical": "Docker", "display_name": "Docker"},
]


def normalize_prep_skill(skill_input: str) -> str:
    if not skill_input:
        return "Python"
    cleaned = skill_input.strip().lower()
    if cleaned in ("sql", "postgres", "postgresql", "sql / postgresql"):
        return "PostgreSQL"
    if cleaned in ("python", "py", "python3"):
        return "Python"
    if cleaned in ("react", "reactjs", "react.js"):
        return "React"
    if cleaned in ("javascript", "js"):
        return "JavaScript"
    if cleaned in ("docker", "containerization"):
        return "Docker"
    return skill_input.strip()


def get_skill_display_name(canonical_skill: str) -> str:
    cleaned = canonical_skill.strip().lower()
    for item in INTERVIEW_PREP_SKILLS:
        if item["canonical"].lower() == cleaned or item["key"] == cleaned:
            return item["display_name"]
    return canonical_skill


def get_attempts_for_user_and_skill(db: Session, user_id: int, canonical_skill: str) -> List[AssessmentAttempt]:
    variants = get_skill_variants(canonical_skill)
    variants_lower = [v.lower() for v in variants]
    if canonical_skill.lower() == "postgresql" and "sql" not in variants_lower:
        variants_lower.append("sql")

    all_user_attempts = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.completed_at.isnot(None),
        )
        .order_by(AssessmentAttempt.completed_at.asc(), AssessmentAttempt.id.asc())
        .all()
    )

    matched = []
    for att in all_user_attempts:
        if att.skill.strip().lower() in variants_lower or att.skill.strip().lower() == canonical_skill.lower():
            matched.append(att)
    return matched


def calculate_attempt_score(db: Session, attempt_id: int) -> float:
    answers = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == attempt_id).all()
    if answers:
        total_q = len(answers)
        correct_q = sum(1 for a in answers if a.is_correct)
        if total_q > 0:
            return round(correct_q / total_q, 4)
    scores = extract_assessment_scores(db, {"attempt_id": attempt_id})
    return float(scores.get("total_score", 0.0)) if (scores and scores.get("total_score") is not None) else 0.0


def calculate_attempt_time_per_question(db: Session, attempt_id: int) -> Optional[float]:
    answers = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == attempt_id).all()
    if not answers:
        return None
    valid_times = [float(str(a.time_taken)) for a in answers if a.time_taken is not None]
    if not valid_times:
        return None
    return round(sum(valid_times) / len(valid_times), 1)


def get_interview_prep_summary(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Computes overall Interview Prep Hub metrics across all supported skills
    using authentic completed assessment attempts and answers.
    """
    skills_data = []
    total_attempts_count = 0
    skills_practised_count = 0
    improving_count = 0
    all_scores = []
    all_times = []

    for skill_meta in INTERVIEW_PREP_SKILLS:
        canonical = skill_meta["canonical"]
        display_name = skill_meta["display_name"]

        attempts = get_attempts_for_user_and_skill(db, user_id, canonical)
        attempts_count = len(attempts)

        if attempts_count == 0:
            skills_data.append({
                "skill": canonical,
                "display_name": display_name,
                "attempts_count": 0,
                "latest_score": None,
                "latest_score_pct": None,
                "first_score": None,
                "first_score_pct": None,
                "best_score": None,
                "best_score_pct": None,
                "average_score": None,
                "average_score_pct": None,
                "trend": "not_started",
                "trend_label": "Not Started",
                "latest_attempt_id": None,
                "latest_completed_at": None,
                "recommendation": f"Take the {display_name} assessment to benchmark your starting technical level."
            })
            continue

        skills_practised_count += 1
        total_attempts_count += attempts_count

        attempt_scores: List[float] = []
        attempt_levels: List[str] = []

        for att in attempts:
            t_score = calculate_attempt_score(db, att.id)
            attempt_scores.append(t_score)
            attempt_levels.append((att.assessed_level or "basic").lower())
            all_scores.append(t_score)

            tpq = calculate_attempt_time_per_question(db, att.id)
            if tpq is not None:
                all_times.append(tpq)

        first_score = attempt_scores[0]
        latest_score = attempt_scores[-1]
        best_score = max(attempt_scores)
        avg_score = round(sum(attempt_scores) / len(attempt_scores), 4)

        latest_att = attempts[-1]
        latest_completed_at = latest_att.completed_at.isoformat() if latest_att.completed_at else None

        # Determine trend based on multiple attempts and level difficulty
        if attempts_count == 1:
            trend = "insufficient_data"
            trend_label = "First Attempt"
            recommendation = f"Completed initial assessment. Take another assessment to unlock progression tracking."
        else:
            prev_score = attempt_scores[-2]
            prev_lvl_val = LEVEL_MAP.get(attempt_levels[-2], 1)
            curr_lvl_val = LEVEL_MAP.get(attempt_levels[-1], 1)

            score_diff = latest_score - prev_score
            lvl_diff = curr_lvl_val - prev_lvl_val

            if lvl_diff > 0 or (lvl_diff == 0 and score_diff > 0.02):
                trend = "improving"
                trend_label = "Improving"
                improving_count += 1
                recommendation = "Keep practising advanced concepts and edge cases to maintain steady growth."
            elif lvl_diff < 0 or (lvl_diff == 0 and score_diff < -0.05):
                trend = "needs_focus"
                trend_label = "Needs Focus"
                recommendation = "Review missed topics and focus on foundational fundamentals before retaking."
            else:
                if latest_score >= 0.70:
                    trend = "on_track"
                    trend_label = "On Track"
                    improving_count += 1
                    recommendation = "Strong, stable performance. Challenge yourself with higher difficulty questions."
                else:
                    trend = "needs_focus"
                    trend_label = "Needs Focus"
                    recommendation = "Score is consistent but below benchmark. Practice targeted question sets."

        skills_data.append({
            "skill": canonical,
            "display_name": display_name,
            "attempts_count": attempts_count,
            "latest_score": latest_score,
            "latest_score_pct": int(round(latest_score * 100)),
            "first_score": first_score,
            "first_score_pct": int(round(first_score * 100)),
            "best_score": best_score,
            "best_score_pct": int(round(best_score * 100)),
            "average_score": avg_score,
            "average_score_pct": int(round(avg_score * 100)),
            "trend": trend,
            "trend_label": trend_label,
            "latest_attempt_id": latest_att.id,
            "latest_completed_at": latest_completed_at,
            "recommendation": recommendation
        })

    # Generate overarching progress text and data-backed key takeaways
    total_supported = len(INTERVIEW_PREP_SKILLS)
    if skills_practised_count == 0:
        overall_progress_text = "You haven't completed any assessments yet. Start with any skill below to begin tracking your improvement."
    elif skills_practised_count == 1:
        overall_progress_text = f"You've started with 1 out of {total_supported} skills. Take additional assessments to unlock trend comparisons."
    else:
        overall_progress_text = f"You've shown improvement in {improving_count} out of {skills_practised_count} practised skills. Keep testing regularly to build consistency."

    key_takeaways = []
    if all_scores:
        avg_all_pct = int(round((sum(all_scores) / len(all_scores)) * 100))
        key_takeaways.append(f"Your overall average score is {avg_all_pct}% across all completed assessments.")

    improving_skills = [s["display_name"] for s in skills_data if s["trend"] in ("improving", "on_track")]
    if improving_skills:
        key_takeaways.append(f"{', '.join(improving_skills[:2])} demonstrate steady technical consistency.")

    focus_skills = [s["display_name"] for s in skills_data if s["trend"] == "needs_focus"]
    if focus_skills:
        key_takeaways.append(f"{', '.join(focus_skills[:2])} would benefit from targeted topic practice.")

    if all_times:
        avg_time = int(round(sum(all_times) / len(all_times)))
        key_takeaways.append(f"You spend an average of {avg_time}s per question across your assessments.")
    else:
        key_takeaways.append("Take regular assessments to measure both accuracy and answering speed.")

    return {
        "total_attempts": total_attempts_count,
        "skills_practised": skills_practised_count,
        "skills_supported_count": total_supported,
        "improving_count": improving_count,
        "overall_progress_text": overall_progress_text,
        "skills": skills_data,
        "key_takeaways": key_takeaways,
    }


def get_skill_analysis_detail(db: Session, user_id: int, skill_input: str) -> Dict[str, Any]:
    """
    Returns in-depth analysis for an individual skill:
    - Attempt metrics (Total, Latest, First, Best, Average, Delta)
    - Chronological score progression chart data
    - Performance trend analysis with difficulty context
    - Past attempts list with view-review link
    """
    canonical = normalize_prep_skill(skill_input)
    display_name = get_skill_display_name(canonical)

    attempts = get_attempts_for_user_and_skill(db, user_id, canonical)
    total_attempts = len(attempts)

    if total_attempts == 0:
        return {
            "skill": canonical,
            "display_name": display_name,
            "total_attempts": 0,
            "latest_score": None,
            "latest_score_pct": None,
            "first_score": None,
            "first_score_pct": None,
            "score_delta_vs_first": None,
            "score_delta_vs_prev": None,
            "best_score": None,
            "best_score_pct": None,
            "average_score": None,
            "average_score_pct": None,
            "average_time_per_question": None,
            "trend": "not_started",
            "trend_label": "Not Started",
            "trend_explanation": f"You haven't completed any assessments for {display_name} yet. Take an assessment to start your benchmark.",
            "difficulty_note": "Note: Scores reflect adaptive question sets from basic to advanced levels.",
            "score_progression": [],
            "past_attempts": [],
        }

    score_progression = []
    past_attempts = []
    scores_list: List[float] = []
    times_list: List[float] = []

    for idx, att in enumerate(attempts):
        total_score = calculate_attempt_score(db, att.id)
        score_pct = int(round(total_score * 100))
        scores_list.append(total_score)

        time_per_q = calculate_attempt_time_per_question(db, att.id)
        if time_per_q is not None:
            times_list.append(time_per_q)

        answers_count = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == att.id).count()
        correct_count = (
            db.query(AssessmentAnswer)
            .filter(AssessmentAnswer.attempt_id == att.id, AssessmentAnswer.is_correct == True)
            .count()
        )

        date_str = att.completed_at.strftime("%b %d, %Y") if att.completed_at else f"Attempt #{idx + 1}"

        score_progression.append({
            "attempt_number": idx + 1,
            "attempt_id": att.id,
            "score": total_score,
            "score_pct": score_pct,
            "assessed_level": att.assessed_level,
            "date": date_str,
            "completed_at": att.completed_at.isoformat() if att.completed_at else None,
        })

        past_attempts.append({
            "attempt_number": idx + 1,
            "attempt_id": att.id,
            "date": date_str,
            "score": total_score,
            "score_pct": score_pct,
            "time_per_question": time_per_q,
            "assessed_level": att.assessed_level,
            "required_level": att.required_level,
            "total_questions": answers_count,
            "correct_answers": correct_count,
        })

    # Reverse past attempts so the newest appears at the top of the table
    past_attempts_reversed = list(reversed(past_attempts))

    first_score = scores_list[0]
    latest_score = scores_list[-1]
    best_score = max(scores_list)
    avg_score = round(sum(scores_list) / len(scores_list), 4)

    first_score_pct = int(round(first_score * 100))
    latest_score_pct = int(round(latest_score * 100))
    best_score_pct = int(round(best_score * 100))
    avg_score_pct = int(round(avg_score * 100))

    score_delta_vs_first = latest_score_pct - first_score_pct
    score_delta_vs_prev = (latest_score_pct - int(round(scores_list[-2] * 100))) if len(scores_list) >= 2 else None

    avg_tpq = round(sum(times_list) / len(times_list), 1) if times_list else None

    # Trend calculation and explainability
    if total_attempts == 1:
        trend = "insufficient_data"
        trend_label = "First Attempt"
        trend_explanation = (
            f"You completed your first assessment for {display_name} with a score of {latest_score_pct}%. "
            "At least two completed attempts are required to determine an improvement trajectory."
        )
    else:
        prev_score = scores_list[-2]
        prev_score_pct = int(round(prev_score * 100))
        delta_first = score_delta_vs_first

        if delta_first > 0:
            trend = "improving"
            trend_label = "Improving"
            trend_explanation = (
                f"Your latest score is {delta_first}% higher than your first attempt. "
                "Keep practising to build consistency across varied question sets."
            )
        elif delta_first < 0:
            trend = "needs_focus"
            trend_label = "Needs Focus"
            trend_explanation = (
                f"Your latest score ({latest_score_pct}%) is lower than your initial score ({first_score_pct}%). "
                "Review the explanations in your past attempts to revisit missed concepts."
            )
        else:
            if latest_score >= 0.70:
                trend = "on_track"
                trend_label = "On Track"
                trend_explanation = (
                    f"Your performance has remained consistent at {latest_score_pct}%. "
                    "Try tackling advanced level questions to push your boundaries."
                )
            else:
                trend = "inconsistent"
                trend_label = "Inconsistent"
                trend_explanation = (
                    f"Your score has held steady around {latest_score_pct}%. "
                    "Targeted practice on your weakest sub-topics will help break through to the next level."
                )

    difficulty_note = "Note: Scores may vary based on difficulty level and question sets."

    return {
        "skill": canonical,
        "display_name": display_name,
        "total_attempts": total_attempts,
        "latest_score": latest_score,
        "latest_score_pct": latest_score_pct,
        "first_score": first_score,
        "first_score_pct": first_score_pct,
        "score_delta_vs_first": score_delta_vs_first,
        "score_delta_vs_prev": score_delta_vs_prev,
        "best_score": best_score,
        "best_score_pct": best_score_pct,
        "average_score": avg_score,
        "average_score_pct": avg_score_pct,
        "average_time_per_question": avg_tpq,
        "trend": trend,
        "trend_label": trend_label,
        "trend_explanation": trend_explanation,
        "difficulty_note": difficulty_note,
        "score_progression": score_progression,
        "past_attempts": past_attempts_reversed,
    }


def get_personalized_next_steps(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Analyzes candidate's real answer records to identify concrete weaknesses,
    prioritizing repeated mistakes and persistent error topics.
    """
    user_attempts = (
        db.query(AssessmentAttempt)
        .filter(AssessmentAttempt.user_id == user_id, AssessmentAttempt.completed_at.isnot(None))
        .all()
    )

    if not user_attempts:
        # Default starting guide when no attempts exist
        return {
            "has_data": False,
            "recommendations": [
                {
                    "skill": "Python",
                    "topic": None,
                    "title": "Start Python Assessment",
                    "priority": "high",
                    "priority_label": "High Priority",
                    "context": "Take your initial assessment to establish your starting proficiency level.",
                    "action_type": "take_assessment",
                    "action_label": "Take Assessment",
                    "practice_url": "/assessment/Python"
                },
                {
                    "skill": "PostgreSQL",
                    "topic": None,
                    "title": "Benchmark SQL & PostgreSQL",
                    "priority": "medium",
                    "priority_label": "Medium Priority",
                    "context": "Verify database querying skills and foundational query knowledge.",
                    "action_type": "take_assessment",
                    "action_label": "Take Assessment",
                    "practice_url": "/assessment/PostgreSQL"
                }
            ],
            "tip": "Focus on one topic at a time. Small, consistent practice leads to better results than trying to fix everything at once."
        }

    attempt_ids = [a.id for a in user_attempts]

    # Query all answers with their associated questions
    answers_query = (
        db.query(AssessmentAnswer, AssessmentQuestion)
        .join(AssessmentQuestion, AssessmentAnswer.question_id == AssessmentQuestion.id)
        .filter(AssessmentAnswer.attempt_id.in_(attempt_ids))
        .all()
    )

    # Aggregate by (skill, topic)
    topic_stats: Dict[str, Dict[str, Any]] = {}
    for ans, q in answers_query:
        skill = normalize_prep_skill(q.skill)
        topic = (q.topic or "General Concepts").strip()
        key = f"{skill}::{topic}"

        if key not in topic_stats:
            topic_stats[key] = {
                "skill": skill,
                "topic": topic,
                "total": 0,
                "incorrect": 0,
                "correct": 0,
            }
        topic_stats[key]["total"] += 1
        if ans.is_correct:
            topic_stats[key]["correct"] += 1
        else:
            topic_stats[key]["incorrect"] += 1

    recommendations = []

    # 1. Identify high priority repeated errors (incorrect >= 2 and accuracy < 0.60)
    for key, stat in topic_stats.items():
        tot = stat["total"]
        inc = stat["incorrect"]
        acc = stat["correct"] / tot if tot > 0 else 1.0

        if inc >= 2 and acc < 0.60:
            skill = stat["skill"]
            topic = stat["topic"]
            acc_pct = int(round(acc * 100))
            recommendations.append({
                "skill": skill,
                "topic": topic,
                "title": f"Review {skill} {topic}",
                "priority": "high",
                "priority_label": "High Priority",
                "context": f"You missed {inc} of your last {tot} {topic} questions ({acc_pct}% accuracy).",
                "action_type": "practice_topic",
                "action_label": "Practice Related Questions",
                "practice_url": f"/assessment/{skill}?topic={topic}"
            })

    # 2. Identify medium priority weaknesses (at least 1 incorrect and accuracy < 0.70)
    if len(recommendations) < 3:
        for key, stat in topic_stats.items():
            tot = stat["total"]
            inc = stat["incorrect"]
            acc = stat["correct"] / tot if tot > 0 else 1.0

            if inc >= 1 and acc < 0.70 and not any(r["skill"] == stat["skill"] and r["topic"] == stat["topic"] for r in recommendations):
                skill = stat["skill"]
                topic = stat["topic"]
                acc_pct = int(round(acc * 100))
                recommendations.append({
                    "skill": skill,
                    "topic": topic,
                    "title": f"Revisit {topic}",
                    "priority": "medium",
                    "priority_label": "Medium Priority",
                    "context": f"Accuracy is {acc_pct}% on {topic}. Reinforce key principles before progressing.",
                    "action_type": "practice_topic",
                    "action_label": "Practice Related Questions",
                    "practice_url": f"/assessment/{skill}?topic={topic}"
                })

    # 3. Add positive reinforcement / next-level challenge for strong skills
    for skill_meta in INTERVIEW_PREP_SKILLS:
        skill = skill_meta["canonical"]
        attempts = get_attempts_for_user_and_skill(db, user_id, skill)
        if attempts and len(recommendations) < 4:
            latest_att = attempts[-1]
            scores = extract_assessment_scores(db, {"attempt_id": latest_att.id})
            t_score = scores.get("total_score", 0.0) if scores else 0.0
            if t_score >= 0.70 and not any(r["skill"] == skill for r in recommendations):
                recommendations.append({
                    "skill": skill,
                    "topic": None,
                    "title": f"Keep Practising {skill}",
                    "priority": "low",
                    "priority_label": "Low Priority",
                    "context": "You're showing steady improvement. Consider challenging a higher difficulty level.",
                    "action_type": "take_assessment",
                    "action_label": "Take Next Assessment",
                    "practice_url": f"/assessment/{skill}"
                })

    # 4. If still few recommendations, recommend unassessed skills
    for skill_meta in INTERVIEW_PREP_SKILLS:
        skill = skill_meta["canonical"]
        display_name = skill_meta["display_name"]
        attempts = get_attempts_for_user_and_skill(db, user_id, skill)
        if not attempts and len(recommendations) < 4:
            recommendations.append({
                "skill": skill,
                "topic": None,
                "title": f"Assess {display_name}",
                "priority": "medium",
                "priority_label": "Medium Priority",
                "context": f"You haven't assessed {display_name} yet. Benchmark your skill level to complete your profile.",
                "action_type": "take_assessment",
                "action_label": "Take Assessment",
                "practice_url": f"/assessment/{skill}"
            })

    return {
        "has_data": True,
        "recommendations": recommendations[:5],
        "tip": "Focus on one topic at a time. Small, consistent practice leads to better results than trying to fix everything at once."
    }
