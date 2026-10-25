from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.requirement_service import extract_requirements
from ..rate_limiter import limiter, RATE_LIMIT_REQUIREMENTS_ANALYZE

router = APIRouter()


class RequirementRequest(BaseModel):
    text: str


@router.post("/requirements/analyze")
@limiter.limit(RATE_LIMIT_REQUIREMENTS_ANALYZE)
def analyze_requirements(request: Request, payload: RequirementRequest):
    if not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Requirement text cannot be empty"
        )

    result = extract_requirements(payload.text)

    if isinstance(result, dict):
        req_list = result.get("requirements", [])
    elif isinstance(result, list):
        req_list = result
    else:
        req_list = []

    return {
        "input": payload.text,
        "requirements": req_list
    }