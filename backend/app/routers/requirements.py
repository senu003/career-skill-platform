from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.requirement_service import extract_requirements


router = APIRouter()


class RequirementRequest(BaseModel):
    text: str


@router.post("/requirements/analyze")
def analyze_requirements(request: RequirementRequest):

    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Requirement text cannot be empty"
        )

    result = extract_requirements(request.text)

    if isinstance(result, dict):
        req_list = result.get("requirements", [])
    elif isinstance(result, list):
        req_list = result
    else:
        req_list = []

    return {
        "input": request.text,
        "requirements": req_list
    }