from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models import (
    AssessmentAttempt,
    AssessmentAnswer,
    AssessmentQuestion,
    QuestionOption
)
from app.services.assessment_service import normalize_skill, get_supported_skills_list
from app.services.skill_analysis_service import extract_assessment_scores


def get_assessment_review(db: Session, attempt_id: int, current_user_id: int) -> Dict[str, Any]:
    """
    Retrieves a complete question-by-question review of a completed assessment attempt.
    Enforces that the attempt belongs to current_user_id and is completed.
    """
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )

    if attempt.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access review for this attempt."
        )

    if attempt.completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assessment attempt {attempt_id} is not yet completed."
        )

    answers = (
        db.query(AssessmentAnswer)
        .filter(AssessmentAnswer.attempt_id == attempt_id)
        .order_by(AssessmentAnswer.id.asc())
        .all()
    )

    questions_review = []
    total_time = 0.0

    for ans in answers:
        q = db.query(AssessmentQuestion).filter(AssessmentQuestion.id == ans.question_id).first()
        if not q:
            continue

        options_map = {opt.option_key: opt.option_text for opt in q.options}
        user_sel = (ans.selected_answer or "").upper().strip()
        corr_ans = (q.correct_answer or "").upper().strip()
        time_sec = float(str(ans.time_taken)) if ans.time_taken is not None else None
        if time_sec:
            total_time += time_sec

        questions_review.append({
            "question_id": q.id,
            "skill": q.skill,
            "level": q.level,
            "topic": q.topic,
            "question": q.question,
            "options": options_map,
            "selected_answer": user_sel,
            "selected_option_text": options_map.get(user_sel),
            "is_correct": bool(ans.is_correct),
            "correct_answer": corr_ans,
            "correct_option_text": options_map.get(corr_ans),
            "explanation": q.explanation or f"Review the fundamental concepts and practical implementation of {q.topic or q.skill}.",
            "misconception": q.misconception or (f"A common trap is misidentifying edge cases in {q.topic or q.skill}." if not ans.is_correct else None),
            "interview_tip": q.interview_tip or f"In interviews, clearly articulate your reasoning and edge-case handling for {q.topic or q.skill}.",
            "time_taken": time_sec,
            "answered_at": ans.answered_at.isoformat() if ans.answered_at else None
        })

    total_q = len(questions_review)
    correct_q = sum(1 for q in questions_review if q["is_correct"])
    incorrect_q = total_q - correct_q
    accuracy = round(correct_q / total_q, 2) if total_q > 0 else 0.0
    avg_time = round(total_time / total_q, 1) if total_q > 0 else None

    scores = extract_assessment_scores(db, {"attempt_id": attempt.id})
    total_score = scores.get("total_score") if scores else (accuracy * 100 if total_q > 0 else None)

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "analysis_id": attempt.analysis_id,
        "skill": attempt.skill,
        "required_level": attempt.required_level,
        "assessed_level": attempt.assessed_level,
        "total_score": total_score,
        "total_questions": total_q,
        "correct_count": correct_q,
        "correct_answers": correct_q,
        "incorrect_count": incorrect_q,
        "accuracy": accuracy,
        "total_time_seconds": round(total_time, 1) if total_time > 0 else None,
        "avg_time_per_question": avg_time,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "questions": questions_review
    }


def get_user_weakness_analysis(db: Session, user_id: int, analysis_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Rule-based personal weakness finder and targeted revision analyzer.
    Aggregates user's historical answers across all completed attempts,
    groups by skill and topic, and generates explainable recommendations.
    """
    supported_skills = get_supported_skills_list()
    # Normalize skill names for clean aggregation without duplicate aliases
    canonical_supported = []
    seen_canonical = set()
    for s in supported_skills:
        c = normalize_skill(s)
        if c.lower() not in seen_canonical:
            seen_canonical.add(c.lower())
            canonical_supported.append(c)

    completed_attempts = (
        db.query(AssessmentAttempt)
        .filter(
            AssessmentAttempt.user_id == user_id,
            AssessmentAttempt.completed_at.isnot(None)
        )
        .order_by(AssessmentAttempt.completed_at.desc())
        .all()
    )

    if not completed_attempts:
        empty_skills_summary = [
            {
                "skill": sk,
                "attempts_count": 0,
                "latest_score": None,
                "latest_level": None,
                "total_questions_answered": 0,
                "accuracy": 0.0,
                "avg_time_per_question": None,
                "weak_topics": [],
                "strong_topics": [],
                "status": "Not Started"
            }
            for sk in canonical_supported
        ]
        return {
            "has_sufficient_data": False,
            "message": "Complete at least one assessment to discover your weak areas and get targeted revision recommendations.",
            "total_attempts_analyzed": 0,
            "total_assessments_completed": 0,
            "total_questions_analyzed": 0,
            "overall_accuracy": 0.0,
            "skills_summary": empty_skills_summary,
            "weak_topics": [],
            "strong_topics": [],
            "insufficient_data_topics": []
        }

    from app.services.skill_analysis_service import select_eligible_assessment_attempt
    from app.models import Analysis, Job
    import json

    selected_attempts: List[AssessmentAttempt] = []
    if analysis_id is not None:
        analysis_obj = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == user_id).first()
        session_skills = []
        if analysis_obj and analysis_obj.raw_analysis_data:
            try:
                parsed_raw = json.loads(str(analysis_obj.raw_analysis_data))
                if isinstance(parsed_raw, list):
                    session_skills = [s.get("skill") for s in parsed_raw if isinstance(s, dict) and s.get("skill")]
            except Exception:
                pass
        if not session_skills and analysis_obj and analysis_obj.job_id:
            job_obj = db.query(Job).filter(Job.id == analysis_obj.job_id).first()
            if job_obj and job_obj.description:
                try:
                    parsed_job = json.loads(str(job_obj.description))
                    if isinstance(parsed_job, list):
                        session_skills = [s.get("skill") for s in parsed_job if isinstance(s, dict) and s.get("skill")]
                except Exception:
                    pass
        target_skills = session_skills if session_skills else canonical_supported
        for sk in target_skills:
            att = select_eligible_assessment_attempt(db, sk, user_id=user_id, analysis_id=analysis_id, include_prior=True)
            if att and att not in selected_attempts:
                selected_attempts.append(att)
    else:
        for sk in canonical_supported:
            att = select_eligible_assessment_attempt(db, sk, user_id=user_id, analysis_id=None, include_prior=True)
            if att and att not in selected_attempts:
                selected_attempts.append(att)

    if not selected_attempts:
        selected_attempts = completed_attempts

    attempt_ids = [a.id for a in selected_attempts]

    answers_rows = (
        db.query(AssessmentAnswer, AssessmentQuestion, AssessmentAttempt)
        .join(AssessmentQuestion, AssessmentAnswer.question_id == AssessmentQuestion.id)
        .join(AssessmentAttempt, AssessmentAnswer.attempt_id == AssessmentAttempt.id)
        .filter(AssessmentAnswer.attempt_id.in_(attempt_ids))
        .all()
    )

    # Group stats by (canonical_skill, topic)
    topic_data: Dict[str, Dict[str, Any]] = {}
    skill_stats: Dict[str, Dict[str, Any]] = {
        sk.lower(): {
            "canonical_name": sk,
            "attempts": 0,
            "total_answered": 0,
            "correct_count": 0,
            "total_time": 0.0,
            "latest_score": None,
            "latest_level": None,
            "weak_topics": set(),
            "strong_topics": set()
        }
        for sk in canonical_supported
    }

    # Count attempts per skill and track latest attempt score/level
    seen_attempts_for_skill = set()
    for att in completed_attempts:
        sk_canon = normalize_skill(att.skill)
        sk_key = sk_canon.lower()
        if sk_key in skill_stats:
            skill_stats[sk_key]["attempts"] += 1
            if sk_key not in seen_attempts_for_skill:
                seen_attempts_for_skill.add(sk_key)
                skill_stats[sk_key]["latest_level"] = att.assessed_level
                # Extract score for this attempt
                sc = extract_assessment_scores(db, {"attempt_id": att.id})
                if sc and sc.get("total_score") is not None:
                    skill_stats[sk_key]["latest_score"] = float(sc["total_score"])

    total_all_answered = 0
    total_all_correct = 0

    for ans, q, att in answers_rows:
        sk_canon = normalize_skill(q.skill or att.skill)
        sk_key = sk_canon.lower()
        topic_name = (q.topic or "Core Principles").strip()
        combo_key = f"{sk_key}::{topic_name.lower()}"

        if combo_key not in topic_data:
            topic_data[combo_key] = {
                "skill": sk_canon,
                "topic": topic_name,
                "total_answered": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "total_time": 0.0,
                "last_level": q.level or "basic"
            }

        topic_data[combo_key]["total_answered"] += 1
        total_all_answered += 1

        if ans.is_correct:
            topic_data[combo_key]["correct_count"] += 1
            total_all_correct += 1
            if sk_key in skill_stats:
                skill_stats[sk_key]["correct_count"] += 1
        else:
            topic_data[combo_key]["incorrect_count"] += 1

        if ans.time_taken is not None:
            t = float(str(ans.time_taken))
            topic_data[combo_key]["total_time"] += t
            if sk_key in skill_stats:
                skill_stats[sk_key]["total_time"] += t

        if sk_key in skill_stats:
            skill_stats[sk_key]["total_answered"] += 1

    weak_topics_list = []
    strong_topics_list = []
    insufficient_topics_list = []

    for combo_key, tdata in topic_data.items():
        tot = tdata["total_answered"]
        cor = tdata["correct_count"]
        incor = tdata["incorrect_count"]
        acc = round(cor / tot, 2) if tot > 0 else 0.0
        avg_t = round(tdata["total_time"] / tot, 1) if tot > 0 and tdata["total_time"] > 0 else None
        sk_canon = tdata["skill"]
        sk_key = sk_canon.lower()

        # Rule for Weak Topic:
        # Any topic with at least 1 incorrect answer and accuracy < 60%
        is_weak = tot >= 1 and incor >= 1 and acc < 0.60

        # Rule for Strength:
        # Requires at least 2 questions answered and accuracy >= 80%
        is_strong = tot >= 2 and acc >= 0.80

        item: Dict[str, Any] = {
            "skill": sk_canon,
            "topic": tdata["topic"],
            "total_answered": tot,
            "correct_count": cor,
            "incorrect_count": incor,
            "accuracy": acc,
            "avg_time_seconds": avg_t,
            "is_weakness": is_weak,
            "is_strength": is_strong,
            "recommendation": None
        }

        if is_weak:
            pct = int(acc * 100)
            reason = f"Review {tdata['topic']} ({sk_canon}) because you answered {incor} of your last {tot} questions incorrectly ({pct}% accuracy)."
            rec_item = {
                "skill": sk_canon,
                "topic": tdata["topic"],
                "incorrect_count": incor,
                "total_answered": tot,
                "accuracy": acc,
                "accuracy_pct": round(acc * 100, 1),
                "reason": reason,
                "recommendation": reason,
                "priority": "high" if incor >= 3 or acc < 0.40 else "medium",
                "suggested_level": tdata["last_level"]
            }
            weak_topics_list.append(rec_item)
            item["recommendation"] = reason
            if sk_key in skill_stats:
                skill_stats[sk_key]["weak_topics"].add(tdata["topic"])
        elif is_strong:
            item["recommendation"] = f"Strong mastery in {tdata['topic']} with {cor}/{tot} correct answers."
            strong_topics_list.append(item)
            if sk_key in skill_stats:
                skill_stats[sk_key]["strong_topics"].add(tdata["topic"])
        else:
            # 1 question or 1/2 answered (insufficient sample)
            item["recommendation"] = "Practice more questions to establish a reliable evaluation for this topic."
            insufficient_topics_list.append(item)

    # Sort weak topics: highest incorrect count first, lowest accuracy
    weak_topics_list.sort(key=lambda w: (-w["incorrect_count"], w["accuracy"]))
    strong_topics_list.sort(key=lambda s: (-s["accuracy"], -s["total_answered"]))

    # Build final skills summary
    skills_summary_list = []
    for sk in canonical_supported:
        sdata = skill_stats.get(sk.lower(), {})
        tot_q = sdata.get("total_answered", 0)
        cor_q = sdata.get("correct_count", 0)
        acc = round(cor_q / tot_q, 2) if tot_q > 0 else 0.0
        tot_time = sdata.get("total_time", 0.0)
        avg_time = round(tot_time / tot_q, 1) if tot_q > 0 and tot_time > 0 else None

        attempts = sdata.get("attempts", 0)
        if attempts == 0:
            status_str = "Not Started"
        elif len(sdata.get("weak_topics", set())) > 0:
            status_str = "Needs Revision"
        else:
            status_str = "Proficient"

        skills_summary_list.append({
            "skill": sk,
            "attempts_count": attempts,
            "latest_score": sdata.get("latest_score"),
            "latest_level": sdata.get("latest_level"),
            "total_questions_answered": tot_q,
            "accuracy": acc,
            "avg_time_per_question": avg_time,
            "weak_topics": sorted(list(sdata.get("weak_topics", set()))),
            "strong_topics": sorted(list(sdata.get("strong_topics", set()))),
            "status": status_str
        })

    overall_acc = round(total_all_correct / total_all_answered, 2) if total_all_answered > 0 else 0.0
    has_sufficient = len(weak_topics_list) > 0 or len(strong_topics_list) > 0

    if has_sufficient:
        msg = f"Analyzed {len(completed_attempts)} completed assessment(s) across {total_all_answered} questions."
    else:
        msg = "Assessment data recorded, but more question attempts are recommended to identify clear topic trends."

    return {
        "has_sufficient_data": has_sufficient,
        "message": msg,
        "total_attempts_analyzed": len(selected_attempts),
        "total_assessments_completed": len(completed_attempts),
        "total_questions_analyzed": total_all_answered,
        "overall_accuracy": overall_acc,
        "skills_summary": skills_summary_list,
        "weak_topics": weak_topics_list,
        "strong_topics": strong_topics_list,
        "insufficient_data_topics": insufficient_topics_list
    }
