import pytest
from fastapi import HTTPException
from app.services.requirement_service import normalize_requirement_level
from app.services.assessment_service import get_allowed_levels

def test_normalize_requirement_level():
    assert normalize_requirement_level("basic") == "basic"
    assert normalize_requirement_level("Intermediate") == "intermediate"
    assert normalize_requirement_level("ADVANCED") == "advanced"
    
    assert normalize_requirement_level(None) == "unspecified"
    assert normalize_requirement_level("unspecified") == "unspecified"
    assert normalize_requirement_level("unknown") == "unspecified"
    assert normalize_requirement_level("expert") == "unspecified"
    assert normalize_requirement_level("") == "unspecified"

def test_get_allowed_levels_valid():
    assert get_allowed_levels("basic") == ["basic"]
    assert get_allowed_levels("intermediate") == ["basic", "intermediate"]
    assert get_allowed_levels("advanced") == ["basic", "intermediate", "advanced"]

def test_get_allowed_levels_invalid_or_unspecified():
    with pytest.raises(HTTPException) as excinfo:
        get_allowed_levels(None)
    assert excinfo.value.status_code == 400
    assert "unspecified" in excinfo.value.detail

    with pytest.raises(HTTPException) as excinfo:
        get_allowed_levels("unspecified")
    assert excinfo.value.status_code == 400
    assert "unspecified" in excinfo.value.detail

    with pytest.raises(HTTPException) as excinfo:
        get_allowed_levels("expert")
    assert excinfo.value.status_code == 400
    assert "Invalid required_level" in excinfo.value.detail
