from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AssessmentResultSchema(BaseModel):
    attempt_id: Optional[int] = Field(None, description="Assessment attempt ID")
    skill: str = Field(..., description="Skill name")
    required_level: str = Field(..., description="Required skill level")
    assessed_level: Optional[str] = Field(None, description="Assessed candidate skill level")
    level_gap: Optional[int] = Field(None, description="Calculated skill level gap")

    class Config:
        from_attributes = True


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
    evidence: Optional[str] = Field(None, description="Contextual snippet evidence if matched")


class CombinedAnalysisResponseSchema(BaseModel):
    filename: Optional[str] = None
    pages: Optional[int] = None
    matched_skills: List[FinalSkillItemSchema]
    missing_skills: List[FinalSkillItemSchema]
    skills: Optional[List[FinalSkillItemSchema]] = None
    score_data: Optional[Dict[str, Any]] = None

