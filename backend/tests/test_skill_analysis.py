import os
import sys
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentAttempt
from app.services.skill_analysis_service import (
    calculate_level_gap,
    combine_cv_and_assessment,
    get_assessment_result_for_skill
)


class TestSkillAnalysisConnection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_matched_skill_with_no_assessment(self):
        """1. Matched skill with no assessment: assessed_level = null, level_gap = null."""
        cv_result = {
            "matched_skills": [
                {
                    "skill": "React",
                    "level": "intermediate",
                    "importance": "required",
                    "evidence": "Experienced with React.js..."
                }
            ],
            "missing_skills": []
        }

        # Passing empty/None assessments dictionary
        combined = combine_cv_and_assessment(cv_result, db_or_assessments={})
        matched_item = combined["matched_skills"][0]

        self.assertEqual(matched_item["skill"], "React")
        self.assertEqual(matched_item["required_level"], "intermediate")
        self.assertTrue(matched_item["matched"])
        self.assertIsNone(matched_item["cv_level"])
        self.assertIsNone(matched_item["assessed_level"])
        self.assertIsNone(matched_item["level_gap"])
        self.assertEqual(matched_item["evidence"], "Experienced with React.js...")

    def test_02_required_advanced_assessed_advanced(self):
        """2. Required advanced + assessed advanced: level_gap = 0."""
        gap = calculate_level_gap("advanced", "advanced")
        self.assertEqual(gap, 0)

        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS"}
            ],
            "missing_skills": []
        }
        assessments = {
            "JavaScript": {"assessed_level": "advanced"}
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        self.assertEqual(item["assessed_level"], "advanced")
        self.assertEqual(item["level_gap"], 0)

    def test_03_required_advanced_assessed_intermediate(self):
        """3. Required advanced + assessed intermediate: level_gap = 1."""
        gap = calculate_level_gap("advanced", "intermediate")
        self.assertEqual(gap, 1)

        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS"}
            ],
            "missing_skills": []
        }
        assessments = {
            "JavaScript": {"assessed_level": "intermediate"}
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        self.assertEqual(item["assessed_level"], "intermediate")
        self.assertEqual(item["level_gap"], 1)

    def test_04_required_intermediate_assessed_basic(self):
        """4. Required intermediate + assessed basic: level_gap = 1."""
        gap = calculate_level_gap("intermediate", "basic")
        self.assertEqual(gap, 1)

        cv_result = {
            "matched_skills": [
                {"skill": "Python", "level": "intermediate", "importance": "required", "evidence": "py"}
            ],
            "missing_skills": []
        }
        assessments = {
            "Python": {"assessed_level": "basic"}
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        self.assertEqual(item["assessed_level"], "basic")
        self.assertEqual(item["level_gap"], 1)

    def test_05_required_basic_assessed_advanced(self):
        """5. Required basic + assessed advanced: level_gap = 0."""
        gap = calculate_level_gap("basic", "advanced")
        self.assertEqual(gap, 0)

        cv_result = {
            "matched_skills": [
                {"skill": "PostgreSQL", "level": "basic", "importance": "required", "evidence": "postgres"}
            ],
            "missing_skills": []
        }
        assessments = {
            "PostgreSQL": {"assessed_level": "advanced"}
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        self.assertEqual(item["assessed_level"], "advanced")
        self.assertEqual(item["level_gap"], 0)

    def test_06_missing_skill_no_assessed_level_no_level_gap(self):
        """6. Missing skill: no assessed level, no level gap."""
        cv_result = {
            "matched_skills": [],
            "missing_skills": [
                {"skill": "Docker", "level": "basic", "importance": "required"}
            ]
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments={})
        missing_item = combined["missing_skills"][0]

        self.assertEqual(missing_item["skill"], "Docker")
        self.assertFalse(missing_item["matched"])
        self.assertIsNone(missing_item["cv_level"])
        self.assertIsNone(missing_item["assessed_level"])
        self.assertIsNone(missing_item["level_gap"])

    def test_07_assessment_isolation_between_skills(self):
        """7. Assessment result for one skill must not incorrectly modify another skill."""
        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS"},
                {"skill": "React", "level": "intermediate", "importance": "required", "evidence": "React"}
            ],
            "missing_skills": [
                {"skill": "Docker", "level": "basic", "importance": "required"}
            ]
        }
        # Only JavaScript has completed assessment
        assessments = {
            "JavaScript": {"assessed_level": "advanced"}
        }

        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        matched_js = next(item for item in combined["matched_skills"] if item["skill"] == "JavaScript")
        matched_react = next(item for item in combined["matched_skills"] if item["skill"] == "React")
        missing_docker = combined["missing_skills"][0]

        # JavaScript updated correctly
        self.assertEqual(matched_js["assessed_level"], "advanced")
        self.assertEqual(matched_js["level_gap"], 0)

        # React remains unassessed
        self.assertIsNone(matched_react["assessed_level"])
        self.assertIsNone(matched_react["level_gap"])

        # Docker remains unassessed
        self.assertIsNone(missing_docker["assessed_level"])
        self.assertIsNone(missing_docker["level_gap"])

    def test_08_get_assessment_result_api_and_db(self):
        """8. Verify DB querying and endpoint for assessment result with level_gap."""
        attempt = AssessmentAttempt(
            user_id=202,
            skill="JavaScript",
            required_level="advanced",
            cv_level=None,
            assessed_level="intermediate",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        # Verify DB query service
        res = get_assessment_result_for_skill(self.db, "JavaScript", user_id=202)
        self.assertIsNotNone(res)
        self.assertEqual(res["attempt_id"], attempt.id)
        self.assertEqual(res["skill"], "JavaScript")
        self.assertEqual(res["required_level"], "advanced")
        self.assertEqual(res["assessed_level"], "intermediate")
        self.assertEqual(res["level_gap"], 1)

        # Verify GET /assessment/result/{skill} API
        api_res = self.client.get(f"/assessment/result/JavaScript?user_id=202")
        self.assertEqual(api_res.status_code, 200)
        data = api_res.json()
        self.assertEqual(data["attempt_id"], attempt.id)
        self.assertEqual(data["required_level"], "advanced")
        self.assertEqual(data["assessed_level"], "intermediate")
        self.assertEqual(data["level_gap"], 1)

        # Verify GET /assessment/{attempt_id}/result API
        api_res2 = self.client.get(f"/assessment/{attempt.id}/result")
        self.assertEqual(api_res2.status_code, 200)
        data2 = api_res2.json()
        self.assertEqual(data2["level_gap"], 1)

    def test_scenario_01_matched_skill_completed_assessment_at_required_level(self):
        """Scenario 1: Matched skill + completed assessment at required level."""
        attempt = AssessmentAttempt(
            user_id=101,
            skill="JavaScript",
            required_level="advanced",
            cv_level=None,
            assessed_level="advanced",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "Experienced JS"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=101)
        item = res["matched_skills"][0]
        self.assertTrue(item["matched"])
        self.assertIsNone(item["cv_level"])
        self.assertEqual(item["assessed_level"], "advanced")
        self.assertEqual(item["level_gap"], 0)

    def test_scenario_02_matched_skill_completed_assessment_below_required_level(self):
        """Scenario 2: Matched skill + completed assessment below required level."""
        attempt = AssessmentAttempt(
            user_id=102,
            skill="JavaScript",
            required_level="advanced",
            cv_level=None,
            assessed_level="intermediate",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS code"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=102)
        item = res["matched_skills"][0]
        self.assertEqual(item["assessed_level"], "intermediate")
        self.assertEqual(item["level_gap"], 1)

    def test_scenario_03_matched_skill_no_completed_assessment(self):
        """Scenario 3: Matched skill + no completed assessment."""
        attempt = AssessmentAttempt(
            user_id=103,
            skill="React",
            required_level="intermediate",
            cv_level=None,
            assessed_level=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "React", "level": "intermediate", "importance": "required", "evidence": "React"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=103)
        item = res["matched_skills"][0]
        self.assertIsNone(item["assessed_level"])
        self.assertIsNone(item["level_gap"])

    def test_scenario_04_missing_skill(self):
        """Scenario 4: Missing skill strictly returns nulls and matched=False."""
        cv_result = {
            "matched_skills": [],
            "missing_skills": [{"skill": "Docker", "level": "basic", "importance": "required"}]
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=104)
        item = res["missing_skills"][0]
        self.assertFalse(item["matched"])
        self.assertIsNone(item["cv_level"])
        self.assertIsNone(item["assessed_level"])
        self.assertIsNone(item["level_gap"])
        self.assertIsNone(item["evidence"])

    def test_scenario_05_required_level_basic(self):
        """Scenario 5: Required level = basic."""
        attempt = AssessmentAttempt(
            user_id=105,
            skill="PostgreSQL",
            required_level="basic",
            cv_level=None,
            assessed_level="basic",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "PostgreSQL", "level": "basic", "importance": "required", "evidence": "Postgres"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=105)
        item = res["matched_skills"][0]
        self.assertEqual(item["required_level"], "basic")
        self.assertEqual(item["assessed_level"], "basic")
        self.assertEqual(item["level_gap"], 0)

    def test_scenario_06_required_level_intermediate(self):
        """Scenario 6: Required level = intermediate."""
        attempt = AssessmentAttempt(
            user_id=106,
            skill="Python",
            required_level="intermediate",
            cv_level=None,
            assessed_level="basic",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "Python", "level": "intermediate", "importance": "required", "evidence": "Python"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=106)
        item = res["matched_skills"][0]
        self.assertEqual(item["required_level"], "intermediate")
        self.assertEqual(item["assessed_level"], "basic")
        self.assertEqual(item["level_gap"], 1)

    def test_scenario_07_required_level_advanced(self):
        """Scenario 7: Required level = advanced."""
        attempt = AssessmentAttempt(
            user_id=107,
            skill="JavaScript",
            required_level="advanced",
            cv_level=None,
            assessed_level="basic",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=107)
        item = res["matched_skills"][0]
        self.assertEqual(item["required_level"], "advanced")
        self.assertEqual(item["assessed_level"], "basic")
        self.assertEqual(item["level_gap"], 2)

    def test_scenario_08_assessed_level_higher_than_required(self):
        """Scenario 8: Assessed level higher than required returns gap = 0."""
        attempt = AssessmentAttempt(
            user_id=108,
            skill="React",
            required_level="basic",
            cv_level=None,
            assessed_level="advanced",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_result = {
            "matched_skills": [{"skill": "React", "level": "basic", "importance": "required", "evidence": "React"}],
            "missing_skills": []
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=108)
        item = res["matched_skills"][0]
        self.assertEqual(item["assessed_level"], "advanced")
        self.assertEqual(item["level_gap"], 0)

    def test_scenario_09_multiple_skills_different_states(self):
        """Scenario 9: Multiple skills with different assessment states."""
        att1 = AssessmentAttempt(
            user_id=109, skill="JavaScript", required_level="advanced", cv_level=None, assessed_level="advanced",
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc)
        )
        att2 = AssessmentAttempt(
            user_id=109, skill="React", required_level="intermediate", cv_level=None, assessed_level="basic",
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc)
        )
        self.db.add_all([att1, att2])
        self.db.commit()

        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS"},
                {"skill": "React", "level": "intermediate", "importance": "required", "evidence": "React"},
                {"skill": "Python", "level": "basic", "importance": "preferred", "evidence": "Python"}
            ],
            "missing_skills": [
                {"skill": "Docker", "level": "basic", "importance": "required"}
            ]
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=109)

        js_item = next(s for s in res["matched_skills"] if s["skill"] == "JavaScript")
        react_item = next(s for s in res["matched_skills"] if s["skill"] == "React")
        py_item = next(s for s in res["matched_skills"] if s["skill"] == "Python")
        docker_item = res["missing_skills"][0]

        self.assertEqual(js_item["assessed_level"], "advanced")
        self.assertEqual(js_item["level_gap"], 0)

        self.assertEqual(react_item["assessed_level"], "basic")
        self.assertEqual(react_item["level_gap"], 1)

        self.assertIsNone(py_item["assessed_level"])
        self.assertIsNone(py_item["level_gap"])

        self.assertFalse(docker_item["matched"])
        self.assertIsNone(docker_item["assessed_level"])
        self.assertIsNone(docker_item["level_gap"])

    def test_scenario_10_no_assessment_result_available(self):
        """Scenario 10: No assessment result available for any skill."""
        cv_result = {
            "matched_skills": [{"skill": "Ruby", "level": "intermediate", "importance": "required", "evidence": "Ruby"}],
            "missing_skills": [{"skill": "Elixir", "level": "basic", "importance": "required"}]
        }
        res = combine_cv_and_assessment(cv_result, db_or_assessments=self.db, user_id=999)
        matched = res["matched_skills"][0]
        missing = res["missing_skills"][0]

        self.assertTrue(matched["matched"])
        self.assertIsNone(matched["assessed_level"])
        self.assertIsNone(matched["level_gap"])

        self.assertFalse(missing["matched"])
        self.assertIsNone(missing["assessed_level"])
        self.assertIsNone(missing["level_gap"])


if __name__ == "__main__":
    unittest.main()

