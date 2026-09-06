from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class AssessmentResultSchema(BaseModel):
    attempt_id: Optional[int] = Field(None, description="Assessment attempt ID")
    skill: str = Field(..., description="Skill name")
    required_level: str = Field(..., description="Required skill level")
    assessed_level: Optional[str] = Field(None, description="Assessed candidate skill level")
    level_gap: Optional[int] = Field(None, description="Calculated skill level gap")
    total_score: Optional[float] = Field(None, description="Calculated total score")
    is_weakness: bool = Field(False, description="Whether this skill is identified as a weakness")
    weakness_reason: str = Field("NONE", description="Reason for weakness classification")
    priority: Optional[str] = Field(None, description="Priority for recommendation")
    recommendation: Optional[str] = Field(None, description="Recommended action")
    recommendation_reason: Optional[str] = Field(None, description="Explanation for recommendation")
    skill_recommendation: Optional[str] = Field(None, description="Model 1 skill evaluator recommendation")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 1 confidence score")
    improvement_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Predicted probability of skill improvement based on longitudinal ML model")
    completed_at: Optional[str] = Field(None, description="ISO timestamp when attempt was completed")

    model_config = ConfigDict(from_attributes=True)


class FinalSkillItemSchema(BaseModel):
    skill: str = Field(..., description="Skill name")
    level: Optional[str] = Field(None, description="Required skill level (legacy alias)")
    required_level: str = Field(..., description="Required skill level")
    importance: str = Field(..., description="Job requirement importance")
    matched: bool = Field(..., description="Whether skill was matched in CV")
    cv_level: Optional[str] = Field(None, description="CV level (remains null)")
    assessed_level: Optional[str] = Field(None, description="Assessed level from assessment attempt")
    ml_predicted_level: Optional[str] = Field(None, description="ML predicted proficiency level")
    level_gap: Optional[int] = Field(None, description="Calculated level gap")
    total_score: Optional[float] = Field(None, description="Calculated total score")
    is_weakness: bool = Field(False, description="Whether this skill is identified as a weakness")
    weakness_reason: str = Field("NONE", description="Reason for weakness classification")
    priority: Optional[str] = Field(None, description="Priority for recommendation")
    recommendation: Optional[str] = Field(None, description="Recommended action")
    recommendation_reason: Optional[str] = Field(None, description="Explanation for recommendation")
    skill_recommendation: Optional[str] = Field(None, description="Model 1 skill evaluator recommendation")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 1 confidence score")
    evidence: Optional[str] = Field(None, description="Contextual snippet evidence if matched")
    improvement_probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Predicted probability of skill improvement based on longitudinal ML model")


class CombinedAnalysisResponseSchema(BaseModel):
    filename: Optional[str] = None
    pages: Optional[int] = None
    matched_skills: List[FinalSkillItemSchema]
    missing_skills: List[FinalSkillItemSchema]
    skills: Optional[List[FinalSkillItemSchema]] = None
    score_data: Optional[Dict[str, Any]] = None
    final_verdict: Optional[str] = Field(None, description="Model 2 final job recommendation verdict")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 2 confidence score")
    priority_skills: Optional[List[Dict[str, Any]]] = Field(None, description="Top priority skills requiring candidate attention")


