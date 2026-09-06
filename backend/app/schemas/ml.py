from typing import Union, Optional
from pydantic import BaseModel, Field, field_validator


VALID_LEVELS = {"basic", "intermediate", "advanced"}


class MLPredictRequestSchema(BaseModel):
    cv_matched: Union[bool, int] = Field(..., description="Whether the skill was matched in CV (boolean or 0/1)")
    required_level: str = Field(..., description="Required skill level (basic, intermediate, advanced)")
    importance: str = Field(..., description="Requirement importance (e.g. required, preferred)")
    basic_score: float = Field(..., ge=0.0, le=1.0, description="Basic score between 0.0 and 1.0")
    intermediate_score: float = Field(..., ge=0.0, le=1.0, description="Intermediate score between 0.0 and 1.0")
    advanced_score: float = Field(..., ge=0.0, le=1.0, description="Advanced score between 0.0 and 1.0")
    total_score: float = Field(..., ge=0.0, le=1.0, description="Total score between 0.0 and 1.0")

    @field_validator("cv_matched")
    @classmethod
    def validate_cv_matched(cls, v):
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)) and v in (0, 1):
            return int(v)
        raise ValueError(f"cv_matched must be boolean or 0/1, got {v}")

    @field_validator("required_level")
    @classmethod
    def validate_required_level(cls, v):
        clean_v = str(v).lower().strip()
        if clean_v not in VALID_LEVELS:
            raise ValueError(f"required_level must be one of {VALID_LEVELS}, got '{v}'")
        return clean_v

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v):
        clean_v = str(v).lower().strip()
        if not clean_v:
            raise ValueError("importance string cannot be empty")
        return clean_v


class MLPredictResponseSchema(BaseModel):
    predicted_level: str = Field(..., description="ML predicted proficiency level (basic, intermediate, advanced)")


class Model1PredictRequestSchema(BaseModel):
    jd_required_level: Union[int, str] = Field(..., description="Required level (1/basic, 2/intermediate, 3/advanced)")
    cv_parsed_level: Union[int, str, None] = Field(0, description="Parsed CV level (0/none, 1/basic, 2/intermediate, 3/advanced)")
    basic_score: float = Field(0.0, ge=0.0, le=1.0)
    intermediate_score: float = Field(0.0, ge=0.0, le=1.0)
    advanced_score: float = Field(0.0, ge=0.0, le=1.0)
    assessment_score: float = Field(0.0, ge=0.0, le=1.0)
    avg_time_per_question: Optional[float] = Field(None, ge=0.0)
    relative_time: Optional[float] = Field(None, ge=0.0)
    attempt_count: int = Field(1, ge=1)
    previous_best_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    score_gap: Optional[int] = Field(None)
    speed_accuracy: Optional[float] = Field(None)


class Model1PredictResponseSchema(BaseModel):
    recommendation: str = Field(..., description="Model 1 recommendation: Mastered, Upgrade Needed, Speed Practice, Re-learn Basics")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model 1 prediction confidence score")


class PrioritySkillSchema(BaseModel):
    skill: str = Field(..., description="Skill name")
    priority_score: float = Field(..., ge=0.0, le=1.0, description="Calculated priority score")
    reason: str = Field(..., description="Explanation for priority ranking")
    required_level: Optional[str] = Field(None, description="Required skill level")
    assessed_level: Optional[str] = Field(None, description="Assessed skill level")
    level_gap: Optional[int] = Field(None, description="Level gap")
    skill_recommendation: Optional[str] = Field(None, description="Model 1 recommendation")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 1 confidence")


class Model2PredictRequestSchema(BaseModel):
    total_required_skills: int = Field(..., ge=0, description="Total required skills count")
    missing_skills_count: int = Field(..., ge=0, description="Missing skills count")
    average_skill_gap: float = Field(..., ge=0.0, description="Average skill gap")
    overall_assessment_accuracy: float = Field(0.0, ge=0.0, le=1.0, description="Overall assessment accuracy")
    upgrade_needed_count: int = Field(0, ge=0, description="Count of Model 1 Upgrade Needed skills")
    mastered_count: int = Field(0, ge=0, description="Count of Model 1 Mastered skills")
    speed_practice_count: int = Field(0, ge=0, description="Count of Model 1 Speed Practice skills")
    relearn_basics_count: int = Field(0, ge=0, description="Count of Model 1 Re-learn Basics skills")
    assessed_skills_count: int = Field(0, ge=0, description="Assessed skills count")
    assessment_completion_rate: float = Field(0.0, ge=0.0, le=1.0, description="Assessment completion rate")


class Model2PredictResponseSchema(BaseModel):
    final_verdict: str = Field(..., description="Model 2 final verdict: Interview Ready, Short-Term Prep, Major Upskill Required")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model 2 prediction confidence score")
    priority_skills: Optional[list[PrioritySkillSchema]] = Field(None, description="Ranked priority skills")

