from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


from .skill_analysis import FinalSkillItemSchema


class RequirementItemSchema(BaseModel):
    skill: str = Field(..., description="Skill name")
    level: str = Field(..., description="Job required skill level")
    importance: str = Field(..., description="Job importance (required or preferred)")


class MatchedSkillSchema(BaseModel):
    skill: str
    level: str
    importance: str
    evidence: str


class MissingSkillSchema(BaseModel):
    skill: str
    level: str
    importance: str


class SkillScoreSchema(BaseModel):
    total_skills: int
    matched_count: int
    missing_count: int
    score: float


class CVAnalyzeResponseSchema(BaseModel):
    filename: str
    pages: int
    matched_skills: List[FinalSkillItemSchema]
    missing_skills: List[FinalSkillItemSchema]
    skills: Optional[List[FinalSkillItemSchema]] = None
    score_data: Optional[SkillScoreSchema] = None
    final_verdict: Optional[str] = Field(None, description="Model 2 final job recommendation verdict")
    recommendation_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model 2 confidence score")
    priority_skills: Optional[List[Dict[str, Any]]] = Field(None, description="Top priority skills requiring candidate attention")



