from typing import Union
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
