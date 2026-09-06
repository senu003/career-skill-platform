"""
TESTS FOR MODEL 2 INTEGRATION WITH SKILL ANALYSIS SERVICE
"""

import unittest
from app.services.skill_analysis_service import combine_cv_and_assessment


class TestModel2Integration(unittest.TestCase):

    def test_combine_cv_and_assessment_includes_model2_outputs(self):
        cv_matching_result = {
            "filename": "test_cv.pdf",
            "pages": 2,
            "matched_skills": [
                {
                    "skill": "JavaScript",
                    "required_level": "basic",
                    "importance": "required",
                    "matched": True,
                    "evidence": "Matched JavaScript in CV"
                }
            ],
            "missing_skills": [
                {
                    "skill": "React",
                    "required_level": "intermediate",
                    "importance": "required",
                    "matched": False
                }
            ],
            "score_data": {
                "total_skills": 2,
                "matched_count": 1,
                "missing_count": 1,
                "score": 50.0
            }
        }

        # Call combine_cv_and_assessment with mock assessment data
        mock_assessments = {
            "JavaScript": {
                "assessed_level": "basic",
                "total_score": 0.85,
                "basic_score": 0.80,
                "intermediate_score": 0.85,
                "advanced_score": 0.90
            }
        }

        res = combine_cv_and_assessment(cv_matching_result, db_or_assessments=mock_assessments)

        self.assertIn("final_verdict", res)
        self.assertIn(res["final_verdict"], ["Interview Ready", "Short-Term Prep", "Major Upskill Required"])

        self.assertIn("recommendation_confidence", res)
        self.assertIsInstance(res["recommendation_confidence"], float)

        self.assertIn("priority_skills", res)
        self.assertIsInstance(res["priority_skills"], list)
        self.assertGreater(len(res["priority_skills"]), 0)

        # Check structure of top priority skill
        top_priority = res["priority_skills"][0]
        self.assertIn("skill", top_priority)
        self.assertIn("priority_score", top_priority)
        self.assertIn("reason", top_priority)

        # Verify existing response structures remain intact (no breaking changes)
        self.assertEqual(res["filename"], "test_cv.pdf")
        self.assertEqual(res["pages"], 2)
        self.assertEqual(len(res["matched_skills"]), 1)
        self.assertEqual(len(res["missing_skills"]), 1)
        self.assertEqual(len(res["skills"]), 2)


if __name__ == "__main__":
    unittest.main()
