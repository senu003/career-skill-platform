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
    analysis_id: Optional[int] = Field(None, description="CV/JD analysis session this assessment belongs to")
    topic: Optional[str] = Field(None, description="Optional specific topic to prioritize for targeted revision")

    @field_validator("required_level")
    def validate_level(cls, v: str) -> str:
        v_clean = v.lower().strip()
        if v_clean not in ["basic", "intermediate", "advanced"]:
            raise ValueError("required_level must be one of: basic, intermediate, advanced")
        return v_clean


class StartAssessmentResponse(BaseModel):
    attempt_id: int
    analysis_id: Optional[int] = None
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
    analysis_id: Optional[int] = None
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


class QuestionReviewItem(BaseModel):
    question_id: int
    skill: str
    level: str
    topic: Optional[str] = None
    question: str
    options: Dict[str, str]
    selected_answer: str
    selected_option_text: Optional[str] = None
    is_correct: bool
    correct_answer: str
    correct_option_text: Optional[str] = None
    explanation: Optional[str] = None
    misconception: Optional[str] = None
    interview_tip: Optional[str] = None
    time_taken: Optional[float] = None
    answered_at: Optional[str] = None


class AssessmentReviewResponse(BaseModel):
    attempt_id: int
    user_id: Optional[int] = None
    analysis_id: Optional[int] = None
    skill: str
    required_level: str
    assessed_level: Optional[str] = None
    total_score: Optional[float] = None
    total_questions: int
    correct_count: int
    correct_answers: int = 0
    incorrect_count: int
    accuracy: float
    total_time_seconds: Optional[float] = None
    avg_time_per_question: Optional[float] = None
    completed_at: Optional[str] = None
    questions: List[QuestionReviewItem]


class TopicPerformanceItem(BaseModel):
    skill: str
    topic: str
    total_answered: int
    correct_count: int
    incorrect_count: int
    accuracy: float
    avg_time_seconds: Optional[float] = None
    is_weakness: bool
    is_strength: bool
    recommendation: Optional[str] = None


class SkillRevisionSummary(BaseModel):
    skill: str
    attempts_count: int
    latest_score: Optional[float] = None
    latest_level: Optional[str] = None
    total_questions_answered: int
    accuracy: float
    avg_time_per_question: Optional[float] = None
    weak_topics: List[str] = []
    strong_topics: List[str] = []
    status: str  # "Needs Revision", "Proficient", "Not Started"


class WeaknessRevisionRecommendation(BaseModel):
    skill: str
    topic: str
    incorrect_count: int
    total_answered: int
    accuracy: float
    accuracy_pct: Optional[float] = None
    reason: str
    recommendation: Optional[str] = None
    priority: str
    suggested_level: str


class TargetedRevisionResponse(BaseModel):
    has_sufficient_data: bool
    message: str
    total_attempts_analyzed: int
    total_assessments_completed: int = 0
    total_questions_analyzed: int
    overall_accuracy: float
    skills_summary: List[SkillRevisionSummary]
    weak_topics: List[WeaknessRevisionRecommendation]
    strong_topics: List[TopicPerformanceItem]
    insufficient_data_topics: List[TopicPerformanceItem]


class InterviewPrepSkillCard(BaseModel):
    skill: str
    display_name: str
    attempts_count: int
    latest_score: Optional[float] = None
    latest_score_pct: Optional[int] = None
    first_score: Optional[float] = None
    first_score_pct: Optional[int] = None
    best_score: Optional[float] = None
    best_score_pct: Optional[int] = None
    average_score: Optional[float] = None
    average_score_pct: Optional[int] = None
    trend: str  # 'improving', 'needs_focus', 'on_track', 'not_started', 'insufficient_data'
    trend_label: str  # 'Improving', 'Needs Focus', 'On Track', 'Not Started', 'First Attempt'
    latest_attempt_id: Optional[int] = None
    latest_completed_at: Optional[str] = None
    recommendation: str


class InterviewPrepSummaryResponse(BaseModel):
    total_attempts: int
    skills_practised: int
    skills_supported_count: int
    improving_count: int
    overall_progress_text: str
    skills: List[InterviewPrepSkillCard]
    key_takeaways: List[str]


class ScoreProgressionPoint(BaseModel):
    attempt_number: int
    attempt_id: int
    score: float
    score_pct: int
    assessed_level: Optional[str] = None
    date: str
    completed_at: Optional[str] = None


class PastAttemptItem(BaseModel):
    attempt_number: int
    attempt_id: int
    date: str
    score: float
    score_pct: int
    time_per_question: Optional[float] = None
    assessed_level: Optional[str] = None
    required_level: str
    total_questions: int
    correct_answers: int


class SkillAnalysisDetailResponse(BaseModel):
    skill: str
    display_name: str
    total_attempts: int
    latest_score: Optional[float] = None
    latest_score_pct: Optional[int] = None
    first_score: Optional[float] = None
    first_score_pct: Optional[int] = None
    score_delta_vs_first: Optional[int] = None
    score_delta_vs_prev: Optional[int] = None
    best_score: Optional[float] = None
    best_score_pct: Optional[int] = None
    average_score: Optional[float] = None
    average_score_pct: Optional[int] = None
    average_time_per_question: Optional[float] = None
    trend: str
    trend_label: str
    trend_explanation: str
    difficulty_note: str
    score_progression: List[ScoreProgressionPoint]
    past_attempts: List[PastAttemptItem]


class PersonalizedNextStepItem(BaseModel):
    skill: str
    topic: Optional[str] = None
    title: str
    priority: str  # 'high', 'medium', 'low'
    priority_label: str  # 'High Priority', 'Medium Priority', 'Low Priority'
    context: str
    action_type: str  # 'practice_topic', 'take_assessment'
    action_label: str  # 'Practice Related Questions', 'Take Next Assessment'
    practice_url: str


class PersonalizedNextStepsResponse(BaseModel):
    has_data: bool
    recommendations: List[PersonalizedNextStepItem]
    tip: str



