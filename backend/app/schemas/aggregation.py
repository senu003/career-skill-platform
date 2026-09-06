from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.skill_analysis import FinalSkillItemSchema

class PrioritySummarySchema(BaseModel):
    high: int = Field(0, description="Count of HIGH priority recommendations")
    medium: int = Field(0, description="Count of MEDIUM priority recommendations")
    low: int = Field(0, description="Count of LOW priority recommendations")

class AggregateRequestSchema(BaseModel):
    skills: List[FinalSkillItemSchema]

class FinalAssessmentAggregationSchema(BaseModel):
    overall_score: Optional[float] = Field(None, description="Weighted overall score of assessed skills")
    total_skills: int = Field(..., description="Total number of skills")
    skills_meeting_requirement: int = Field(..., description="Count of skills meeting the required level")
    skills_below_requirement: int = Field(..., description="Count of skills below the required level")
    weakness_count: int = Field(..., description="Total number of weaknesses identified")
    priority_summary: PrioritySummarySchema
    strongest_skills: List[str] = Field(default_factory=list, description="Top 3 strongest skills")
    weakest_skills: List[str] = Field(default_factory=list, description="Top 3 weakest skills")
    required_skills_summary: str = Field(..., description="Summary of required skills status")
    preferred_skills_summary: str = Field(..., description="Summary of preferred skills status")
    readiness_status: str = Field(..., description="Overall readiness string (e.g., Excellent, Needs Improvement)")
    final_verdict: Optional[str] = Field(None, description="Model 2 final job recommendation verdict")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 2 confidence score")
    overall_improvement_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Aggregated candidate skill improvement probability across skills with valid longitudinal history")
    skills: List[FinalSkillItemSchema] = Field(..., description="Complete individual skill results")
