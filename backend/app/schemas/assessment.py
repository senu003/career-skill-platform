from typing import List, Dict, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class QuestionSchema(BaseModel):
    id: int
    skill: str
    level: str
    topic: Optional[str] = None
    question: str
    question_type: str = "MCQ"
    options: Dict[str, str]

    model_config = ConfigDict(from_attributes=True)


class StartAssessmentRequest(BaseModel):
    skill: str = Field(..., description="Skill name (JavaScript, React, PostgreSQL)")
    required_level: str = Field(..., description="basic, intermediate, or advanced")
    user_id: Optional[int] = Field(None, description="Optional User ID")

    @field_validator("required_level")
    def validate_level(cls, v: str) -> str:
        v_clean = v.lower().strip()
        if v_clean not in ["basic", "intermediate", "advanced"]:
            raise ValueError("required_level must be one of: basic, intermediate, advanced")
        return v_clean


class StartAssessmentResponse(BaseModel):
    attempt_id: int
    skill: str
    required_level: str
    cv_level: Optional[str] = None
    current_level: str
    status: str
    questions: List[QuestionSchema]


class SubmitAnswerRequest(BaseModel):
    attempt_id: int = Field(..., description="ID of active assessment attempt")
    question_id: int = Field(..., description="ID of question being answered")
    selected_answer: str = Field(..., description="Answer option (A, B, C, D)")
    time_taken: Optional[float] = Field(None, ge=0.0, description="Time taken to answer question in seconds")

    @field_validator("selected_answer")
    def validate_selected_answer(cls, v: str) -> str:
        if not v or v.upper().strip() not in ["A", "B", "C", "D"]:
            raise ValueError("selected_answer must be one of 'A', 'B', 'C', 'D'")
        return v.upper().strip()


class SubmitAnswerResponse(BaseModel):
    attempt_id: int
    question_id: int
    selected_answer: str
    is_correct: bool
    level_completed: bool
    level_passed: Optional[bool] = None
    attempt_completed: bool
    assessed_level: Optional[str] = None
    next_questions: Optional[List[QuestionSchema]] = None


class AnswerDetailSchema(BaseModel):
    question_id: int
    selected_answer: str
    is_correct: bool
    time_taken: Optional[float] = None
    answered_at: str


class AttemptStatusResponse(BaseModel):
    attempt_id: int
    user_id: Optional[int] = None
    skill: str
    required_level: str
    cv_level: Optional[str] = None
    assessed_level: Optional[str] = None
    current_level: Optional[str] = None
    is_completed: bool
    started_at: str
    completed_at: Optional[str] = None
    answers_count: int
    questions: List[QuestionSchema]
    submitted_answers: List[AnswerDetailSchema] = []


class CompleteAssessmentResponse(BaseModel):
    attempt_id: int
    status: str
    assessed_level: Optional[str] = None
    completed_at: Optional[str] = None

class LongitudinalOutcome(BaseModel):
    score_change: Optional[float] = None
    level_change: Optional[int] = None
    improved: bool
    declined: bool
    persistent_weakness: bool

class AssessmentHistoryObservation(BaseModel):
    attempt_id: int
    skill: str
    required_level: str
    assessed_level: Optional[str] = None
    basic_score: Optional[float] = None
    intermediate_score: Optional[float] = None
    advanced_score: Optional[float] = None
    total_score: Optional[float] = None
    level_gap: Optional[int] = None
    is_weakness: bool
    weakness_reason: str
    priority: str
    completed_at: Optional[str] = None
    outcome: Optional[LongitudinalOutcome] = None

