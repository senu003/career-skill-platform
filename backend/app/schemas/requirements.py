from typing import List, Optional
from pydantic import BaseModel, Field


class RequirementRequest(BaseModel):
    text: str = Field(..., description="Raw text of the job description to extract requirements from")


class RequirementItemSchema(BaseModel):
    skill: str
    level: str
    importance: str


class RequirementAnalysisResponse(BaseModel):
    input: str
    requirements: List[RequirementItemSchema]
