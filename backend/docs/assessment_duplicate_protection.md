# Phase 3C: Duplicate Assessment Protection Architecture

## 1. Executive Summary

CareerSkill Phase 3C establishes atomic transactions and idempotent deduplication for the skill assessment flow. Under high network latency, intermittent mobile disconnects, or multi-worker concurrency:
- Exactly one answer is recorded per question per assessment attempt.
- The answer record and attempt progression/completion are committed within the **same atomic database transaction**.
- Identical retries (e.g. from lost client responses or browser re-submits) safely return the previously computed state without double-counting scores, changing progress, or throwing errors.
- Conflicting duplicate submissions (attempting to alter an already answered question) are rejected with `409 Conflict` while preserving original answers and state.
- Retrying the final question of an assessment safely recovers the completed result, preserving completion timestamps and assessed skill levels.
- Intentional retakes remain independent `AssessmentAttempt` entities with separate progression timelines.

---

## 2. Database Constraint & Deduplication Migration

### Migration `005_answer_uniqueness.py`
Alembic migration revision `005_answer_uniqueness` guarantees database-level integrity across workers:

1. **Deduplication Strategy**:
   Before creating or enforcing the unique constraint, any historical duplicates in `assessment_answers` are pruned, keeping the most recent record (highest primary key `id`):
   ```sql
   DELETE FROM assessment_answers
   WHERE id NOT IN (
       SELECT MAX(id)
       FROM assessment_answers
       GROUP BY attempt_id, question_id
   );
   ```

2. **Composite Unique Constraint**:
   A database-level unique constraint is applied:
   ```sql
   CONSTRAINT unique_attempt_question UNIQUE (attempt_id, question_id)
   ```
   This ensures that no two workers or database connections can persist duplicate answers for the same question within an attempt.

---

## 3. Atomic Transaction Flow (`submit_answer`)

Prior to Phase 3C, the answer record and the attempt progression were committed in separate transactions. If a failure occurred after inserting the answer but before updating attempt progress, the session was left in a corrupt, non-progressed state.

In Phase 3C:
1. **Pipelined Staging**:
   - `AssessmentAnswer` is created and staged via `db.add(answer_record)`.
   - `db.flush()` verifies database constraints early.
2. **Progression State Evaluation**:
   - `evaluate_attempt_state(db, attempt)` calculates active level, level pass/fail, and completion status.
   - If level or attempt is completed, `attempt.assessed_level` and `attempt.completed_at` are staged in the session.
3. **Atomic Commit**:
   - A single `db.commit()` commits both the answer row and attempt mutations together:
   ```python
   try:
       db.commit()
       db.refresh(attempt)
   except Exception:
       db.rollback()
       raise
   ```
   If any exception or disconnection occurs before or during commit, `db.rollback()` removes all staged changes, preserving complete transactional atomicity.

---

## 4. Idempotent Retry & Conflict Handling

### Identification & Ordering
In `submit_answer`, `existing_answer` is evaluated **before** checking `attempt.completed_at`. This ensures that retrying the final question of a completed assessment succeeds rather than prematurely raising `"Assessment attempt is already completed."`:

```python
existing_answer = db.query(AssessmentAnswer).filter(
    AssessmentAnswer.attempt_id == attempt_id,
    AssessmentAnswer.question_id == question_id
).first()

if existing_answer:
    if existing_answer.selected_answer.upper().strip() == sel_ans:
        return _build_existing_answer_response(db, attempt, question, existing_answer)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Duplicate answer conflict: question {question_id} has already been answered with '{existing_answer.selected_answer}'. Conflicting answer '{sel_ans}' is rejected."
    )
```

### Response Reconstruction (`_build_existing_answer_response`)
On safe retry, the response is deterministically reconstructed:
- **`attempt_id`**, **`question_id`**, **`selected_answer`**, and **`is_correct`** are read from `existing_answer`.
- If the question was an intermediate question in an active level, `level_completed = False`, `attempt_completed = False`, `next_questions = None`.
- If the question was the 5th (final) question of a level:
  - `level_completed = True`.
  - `level_passed = (correct_count >= 4)`.
  - If the candidate passed and another level exists, `next_questions` provides the next level's questions.
  - If the attempt ended (failed level or finished all levels), `attempt_completed = True`, `assessed_level = attempt.assessed_level`, and `next_questions = None`.

---

## 5. Worker Concurrency & Race Resolution

When two workers receive simultaneous requests for the same `(attempt_id, question_id)`:
1. Both workers may not find an existing answer initially.
2. The first worker to execute `db.flush()` acquires the table/index lock and proceeds.
3. The second worker's `db.flush()` hits a database constraint violation and raises `sqlalchemy.exc.IntegrityError`.
4. The second worker rolls back its failed transaction, queries the winning record inserted by Worker 1, and:
   - If identical: returns the safe recovered response (`200 OK`).
   - If conflicting: raises `409 Conflict`.

---

## 6. Retake Isolation

Intentional retakes start via `POST /assessment/start`. This creates a brand new `AssessmentAttempt` row with a new primary key `attempt.id`. Answers for the new attempt are keyed by `(new_attempt_id, question_id)`, completely isolating retake attempts from prior attempts and preserving full historical tracking in the Interview Prep Hub and longitudinal telemetry.

