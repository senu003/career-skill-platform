import pytest
from app.schemas.skill_analysis import FinalSkillItemSchema
from app.services.aggregation_service import aggregate_final_assessment

def test_aggregation_empty_skills():
    res = aggregate_final_assessment([])
    assert res.total_skills == 0
    assert res.overall_score is None
    assert res.readiness_status == "Insufficient Data"

def test_aggregation_one_skill():
    skill = FinalSkillItemSchema(
        skill="React",
        required_level="intermediate",
        importance="required",
        matched=True,
        assessed_level="intermediate",
        level_gap=0,
        total_score=0.85,
        is_weakness=False,
        weakness_reason="NONE",
        priority="LOW"
    )
    res = aggregate_final_assessment([skill])
    assert res.total_skills == 1
    assert res.overall_score == 0.85
    assert res.readiness_status == "Excellent"
    assert res.skills_meeting_requirement == 1

def test_aggregation_multiple_skills_all_satisfactory():
    skills = [
        FinalSkillItemSchema(
            skill="React",
            required_level="intermediate",
            importance="required",
            matched=True,
            assessed_level="intermediate",
            level_gap=0,
            total_score=0.75,
            is_weakness=False,
            priority="LOW"
        ),
        FinalSkillItemSchema(
            skill="Python",
            required_level="basic",
            importance="preferred",
            matched=True,
            assessed_level="intermediate",
            level_gap=0,
            total_score=0.90,
            is_weakness=False,
            priority="LOW"
        )
    ]
    res = aggregate_final_assessment(skills)
    assert res.total_skills == 2
    assert res.skills_meeting_requirement == 2
    assert res.readiness_status == "Excellent"
    
    # Weight: required=1.0, preferred=0.5
    # total score: (0.75 * 1.0 + 0.90 * 0.5) / 1.5 = (0.75 + 0.45) / 1.5 = 1.20 / 1.5 = 0.8
    assert res.overall_score == 0.8000
    assert "1/1 required" in res.required_skills_summary
    assert "1/1 preferred" in res.preferred_skills_summary

def test_aggregation_one_weak_skill():
    skill = FinalSkillItemSchema(
        skill="Node",
        required_level="advanced",
        importance="required",
        matched=True,
        assessed_level="basic",
        level_gap=2,
        total_score=0.35,
        is_weakness=True,
        weakness_reason="Level gap > 0",
        priority="HIGH"
    )
    res = aggregate_final_assessment([skill])
    assert res.readiness_status == "Needs Improvement"
    assert res.skills_meeting_requirement == 0
    assert res.skills_below_requirement == 1
    assert res.priority_summary.high == 1
    assert res.weakness_count == 1
    assert res.overall_score == 0.35

def test_aggregation_missing_assessment():
    skill1 = FinalSkillItemSchema(
        skill="Docker",
        required_level="basic",
        importance="required",
        matched=True,
        assessed_level=None,
        level_gap=None,
        total_score=None,
        is_weakness=False,
        priority=None
    )
    res = aggregate_final_assessment([skill1])
    assert res.readiness_status == "Insufficient Data"
    assert res.overall_score is None
    assert res.skills_meeting_requirement == 0
    assert res.skills_below_requirement == 0

def test_aggregation_boundary_scores():
    skills = [
        FinalSkillItemSchema(
            skill="S1",
            required_level="basic",
            importance="required",
            matched=True,
            assessed_level="basic",
            level_gap=0,
            total_score=0.60,
            is_weakness=False,
            priority="LOW"
        ),
        FinalSkillItemSchema(
            skill="S2",
            required_level="basic",
            importance="required",
            matched=True,
            assessed_level="none",
            level_gap=1,
            total_score=0.35,
            is_weakness=True,
            priority="MEDIUM"
        )
    ]
    res = aggregate_final_assessment(skills)
    assert res.total_skills == 2
    assert res.skills_meeting_requirement == 1
    assert res.skills_below_requirement == 1
    assert res.weakness_count == 1
    assert res.priority_summary.medium == 1
    # 50% met, no HIGH priority weakness -> could be Good or Needs Improvement. 
    # assessed_count = 2, skills_below_req = 1. (1 > 2/2) => False. 
    # has_high_req_weakness = False. -> "Good".
    assert res.readiness_status == "Good"
    assert res.overall_score == 0.475  # (0.60 + 0.35) / 2
