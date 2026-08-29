from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models import AssessmentQuestion, QuestionOption, AssessmentAttempt, AssessmentAnswer
from app.schemas.assessment import QuestionSchema

SUPPORTED_SKILLS = {
    "javascript": "JavaScript",
    "react": "React",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "js": "JavaScript"
}

LEVEL_SEQUENCE = ["basic", "intermediate", "advanced"]


def normalize_skill(skill_input: str) -> str:
    cleaned = skill_input.strip().lower()
    if cleaned in SUPPORTED_SKILLS:
        return SUPPORTED_SKILLS[cleaned]
    # Check case-insensitive match in db
    for k, v in SUPPORTED_SKILLS.items():
        if k == cleaned:
            return v
    return skill_input.strip()


def get_allowed_levels(required_level: str) -> List[str]:
    req = required_level.lower().strip()
    if req not in LEVEL_SEQUENCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid required_level '{required_level}'. Must be basic, intermediate, or advanced."
        )
    idx = LEVEL_SEQUENCE.index(req)
    return LEVEL_SEQUENCE[: idx + 1]


def fetch_questions_for_level(db: Session, skill: str, level: str) -> List[Dict[str, Any]]:
    questions = (
        db.query(AssessmentQuestion)
        .filter(
            func.lower(AssessmentQuestion.skill) == skill.lower(),
            func.lower(AssessmentQuestion.level) == level.lower(),
            AssessmentQuestion.is_active == True
        )
        .order_by(AssessmentQuestion.id.asc())
        .all()
    )

    result = []
    for q in questions:
        options_dict = {opt.option_key: opt.option_text for opt in q.options}
        # Explicitly omit correct_answer
        result.append({
            "id": q.id,
            "skill": q.skill,
            "level": q.level,
            "topic": q.topic,
            "question": q.question,
            "options": options_dict
        })
    return result


def evaluate_attempt_state(db: Session, attempt: AssessmentAttempt) -> Tuple[Optional[str], Optional[str], bool, Dict[str, Any]]:
    """
    Evaluates the state of an attempt based on submitted answers.
    Returns:
      (current_active_level, computed_assessed_level, is_completed, summary_stats)
    """
    skill = attempt.skill
    allowed_levels = get_allowed_levels(attempt.required_level)

    # Fetch all answers for this attempt
    answers = (
        db.query(AssessmentAnswer)
        .filter(AssessmentAnswer.attempt_id == attempt.id)
        .all()
    )
    answer_map = {ans.question_id: ans for ans in answers}

    current_active_level = None
    last_passed_level = None
    is_completed = False

    level_stats = {}

    for lvl in allowed_levels:
        lvl_questions = (
            db.query(AssessmentQuestion)
            .filter(
                func.lower(AssessmentQuestion.skill) == skill.lower(),
                func.lower(AssessmentQuestion.level) == lvl.lower(),
                AssessmentQuestion.is_active == True
            )
            .order_by(AssessmentQuestion.id.asc())
            .all()
        )

        lvl_q_ids = [q.id for q in lvl_questions]
        answered_q_ids = [q_id for q_id in lvl_q_ids if q_id in answer_map]

        correct_count = sum(1 for q_id in answered_q_ids if answer_map[q_id].is_correct)
        total_lvl_questions = len(lvl_questions) if lvl_questions else 5

        level_stats[lvl] = {
            "total": total_lvl_questions,
            "answered": len(answered_q_ids),
            "correct": correct_count
        }

        if len(answered_q_ids) < total_lvl_questions:
            # Level still in progress
            current_active_level = lvl
            break
        else:
            # Level finished (5/5 answered)
            if correct_count >= 4:
                # Passed level (4/5 or 5/5)
                last_passed_level = lvl
                # Continue loop to next level if available
            else:
                # Failed level (<= 3/5)
                is_completed = True
                current_active_level = None
                break

    if not is_completed and current_active_level is None:
        # Candidate finished all allowed levels up to required_level
        is_completed = True

    computed_assessed_level = last_passed_level if is_completed else attempt.assessed_level
    return current_active_level, last_passed_level, is_completed, level_stats


def start_assessment(db: Session, skill: str, required_level: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    canonical_skill = normalize_skill(skill)
    allowed_levels = get_allowed_levels(required_level)

    # Check if questions exist for this skill
    q_exists = (
        db.query(AssessmentQuestion)
        .filter(func.lower(AssessmentQuestion.skill) == canonical_skill.lower())
        .first()
    )
    if not q_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported skill '{skill}'. Initial assessment supports: JavaScript, React, PostgreSQL."
        )

    attempt = AssessmentAttempt(
        user_id=user_id,
        skill=canonical_skill,
        required_level=required_level.lower().strip(),
        cv_level=None,  # Rule: CV level = NULL initially
        assessed_level=None,
        started_at=datetime.now(timezone.utc)
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    initial_level = allowed_levels[0]
    questions = fetch_questions_for_level(db, canonical_skill, initial_level)

    return {
        "attempt_id": attempt.id,
        "skill": attempt.skill,
        "required_level": attempt.required_level,
        "cv_level": attempt.cv_level,
        "current_level": initial_level,
        "status": "in_progress",
        "questions": questions
    }


def submit_answer(db: Session, attempt_id: int, question_id: int, selected_answer: str) -> Dict[str, Any]:
    # 1. Fetch attempt
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )

    if attempt.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment attempt is already completed."
        )

    # 2. Fetch question
    question = db.query(AssessmentQuestion).filter(AssessmentQuestion.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question with ID {question_id} not found."
        )

    # 3. Validate answer string
    sel_ans = selected_answer.upper().strip()
    if sel_ans not in ["A", "B", "C", "D"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid selected_answer '{selected_answer}'. Must be A, B, C, or D."
        )

    # 4. Check duplicate answer
    existing_answer = (
        db.query(AssessmentAnswer)
        .filter(
            AssessmentAnswer.attempt_id == attempt_id,
            AssessmentAnswer.question_id == question_id
        )
        .first()
    )
    if existing_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate answer: question {question_id} has already been answered in attempt {attempt_id}."
        )

    # 5. Determine active level before adding answer
    current_active_level, last_passed, is_done, _ = evaluate_attempt_state(db, attempt)
    if is_done or not current_active_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment attempt is already finished."
        )

    if question.skill.lower() != attempt.skill.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question {question_id} belongs to skill '{question.skill}', but attempt is for '{attempt.skill}'."
        )

    if question.level.lower() != current_active_level.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question {question_id} is for level '{question.level}', but current active level is '{current_active_level}'."
        )

    # 6. Save answer
    is_correct = (sel_ans == question.correct_answer.upper())
    answer_record = AssessmentAnswer(
        attempt_id=attempt_id,
        question_id=question_id,
        selected_answer=sel_ans,
        is_correct=is_correct,
        answered_at=datetime.now(timezone.utc)
    )
    db.add(answer_record)
    db.commit()

    # 7. Re-evaluate attempt state
    new_active_level, new_last_passed, new_is_done, level_stats = evaluate_attempt_state(db, attempt)

    level_completed = (new_active_level != current_active_level)
    level_passed = None
    next_questions = None

    if level_completed:
        stats = level_stats.get(current_active_level, {})
        level_passed = (stats.get("correct", 0) >= 4)

        if new_is_done:
            attempt.assessed_level = new_last_passed
            attempt.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(attempt)
        else:
            next_questions = fetch_questions_for_level(db, attempt.skill, new_active_level)
    elif new_is_done:
        attempt.assessed_level = new_last_passed
        attempt.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "question_id": question_id,
        "selected_answer": sel_ans,
        "is_correct": is_correct,
        "level_completed": level_completed,
        "level_passed": level_passed,
        "attempt_completed": attempt.completed_at is not None,
        "assessed_level": attempt.assessed_level,
        "next_questions": next_questions
    }


def get_attempt_details(db: Session, attempt_id: int) -> Dict[str, Any]:
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )

    active_level, last_passed, is_done, _ = evaluate_attempt_state(db, attempt)

    # Sync assessed_level & completed_at if attempt is done but not persisted
    if is_done and attempt.completed_at is None:
        attempt.assessed_level = last_passed
        attempt.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(attempt)

    answers = (
        db.query(AssessmentAnswer)
        .filter(AssessmentAnswer.attempt_id == attempt_id)
        .order_by(AssessmentAnswer.id.asc())
        .all()
    )

    submitted_answers_list = [
        {
            "question_id": ans.question_id,
            "selected_answer": ans.selected_answer,
            "is_correct": ans.is_correct,
            "answered_at": ans.answered_at.isoformat() if ans.answered_at else ""
        }
        for ans in answers
    ]

    target_level = active_level if active_level else (last_passed or "basic")
    questions = fetch_questions_for_level(db, attempt.skill, target_level)

    return {
        "attempt_id": attempt.id,
        "user_id": attempt.user_id,
        "skill": attempt.skill,
        "required_level": attempt.required_level,
        "cv_level": attempt.cv_level,
        "assessed_level": attempt.assessed_level,
        "current_level": active_level if not attempt.completed_at else None,
        "is_completed": attempt.completed_at is not None,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else "",
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "answers_count": len(answers),
        "questions": questions,
        "submitted_answers": submitted_answers_list
    }


def complete_assessment(db: Session, attempt_id: int) -> Dict[str, Any]:
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment attempt {attempt_id} not found."
        )

    if attempt.completed_at is not None:
        return {
            "attempt_id": attempt.id,
            "status": "completed",
            "assessed_level": attempt.assessed_level,
            "completed_at": attempt.completed_at.isoformat()
        }

    active_level, last_passed, is_done, level_stats = evaluate_attempt_state(db, attempt)

    if not is_done and active_level:
        stats = level_stats.get(active_level, {})
        answered = stats.get("answered", 0)
        total = stats.get("total", 5)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark assessment as completed: current level '{active_level}' is still in progress ({answered}/{total} answered)."
        )

    attempt.assessed_level = last_passed
    attempt.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)

    return {
        "attempt_id": attempt.id,
        "status": "completed",
        "assessed_level": attempt.assessed_level,
        "completed_at": attempt.completed_at.isoformat()
    }
