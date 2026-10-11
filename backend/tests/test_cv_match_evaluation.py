import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import AssessmentAttempt
from app.services.requirement_service import evaluate_cv_with_gemini
from app.services.skill_analysis_service import combine_cv_and_assessment


class MockGeminiResponse:
    def __init__(self, data):
        self.parsed = data
        self.text = json.dumps(data)


def mock_gemini_generate_content(model, contents, config=None):
    prompt_str = str(contents)
    
    cv_text_part = prompt_str.split("Candidate CV Text:")[-1] if "Candidate CV Text:" in prompt_str else prompt_str
    
    evaluations = []
    if "React" in prompt_str:
        if "Built multiple React applications" in cv_text_part:
            evaluations.append({
                "skill": "React",
                "cv_level": "intermediate",
                "cv_match_status": "Match",
                "evidence": "Built multiple React applications using hooks, reusable components, routing, and state management.",
                "actionable_feedback": {
                    "section": "Experience",
                    "original_text": "Built multiple React applications",
                    "category": "safe rewrite",
                    "priority": "low",
                    "explanation": "You can highlight specific metrics.",
                    "suggested_wording": "Engineered multiple React applications.",
                    "follow_up_questions": [],
                    "next_action": "Consider updating your CV with this wording."
                }
            })
        elif "Familiar with React" in cv_text_part:
            evaluations.append({
                "skill": "React",
                "cv_level": "basic",
                "cv_match_status": "Needs Improvement",
                "evidence": "CV mentions being familiar with React.",
                "actionable_feedback": {
                    "section": "Skills",
                    "original_text": "Familiar with React",
                    "category": "clarification needed",
                    "priority": "high",
                    "explanation": "Needs more detail.",
                    "suggested_wording": None,
                    "follow_up_questions": ["What projects did you build with React?"],
                    "next_action": "Add specific project details."
                }
            })
    
    if "JavaScript" in prompt_str:
        if "Python and Django" in cv_text_part:
            evaluations.append({
                "skill": "JavaScript",
                "cv_level": "not_found",
                "cv_match_status": "Missing",
                "evidence": None,
                "actionable_feedback": {
                    "section": None,
                    "original_text": None,
                    "category": "requirement not evidenced",
                    "priority": "medium",
                    "explanation": "JavaScript is not mentioned.",
                    "suggested_wording": None,
                    "follow_up_questions": [],
                    "next_action": "Add JavaScript experience if you have it."
                }
            })
    
    if "PostgreSQL" in prompt_str:
        if "simple SELECT queries" in cv_text_part or "Basic exposure" in cv_text_part:
            evaluations.append({
                "skill": "PostgreSQL",
                "cv_level": "basic",
                "cv_match_status": "Needs Improvement",
                "evidence": "Basic exposure / simple SELECT queries."
            })

    if "Python" in prompt_str:
        if "data cleaning and automation" in cv_text_part:
            evaluations.append({
                "skill": "Python",
                "cv_level": "basic",
                "cv_match_status": "Match",
                "evidence": "Wrote Python scripts for data cleaning.",
                "actionable_feedback": {
                    "section": "Projects",
                    "original_text": "Fake original text not in CV",
                    "category": "safe rewrite",
                    "priority": "low",
                    "explanation": "This text doesn't match the CV exactly.",
                    "suggested_wording": "Should be removed because original_text mismatch.",
                    "follow_up_questions": [],
                    "next_action": "Nothing"
                }
            })

    if "Git" in prompt_str:
        if "version control" in cv_text_part:
            evaluations.append({
                "skill": "Git",
                "cv_level": "unspecified",
                "cv_match_status": "Match",
                "evidence": "Used Git for version control."
            })

    return MockGeminiResponse({"evaluations": evaluations})


class TestCVMatchEvaluationScenarios(unittest.TestCase):

    def setUp(self):
        self.db = SessionLocal()
        # Clean up test attempts
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (801, 802)"))
        self.db.commit()
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["GEMINI_MOCK"] = "0"
        os.environ["GEMINI_REFRESH"] = "1"

        # Patch Gemini API client inside requirement_service
        self.patcher = patch("app.services.requirement_service.client.models.generate_content", side_effect=mock_gemini_generate_content)
        self.mock_generate = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.db.close()

    def test_scenario_a_react_intermediate_strong_evidence(self):
        """
        A. Required: React — Intermediate
        CV has strong Intermediate-level evidence.
        Expected: Match
        """
        requirements = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        cv_text = "Built multiple React applications using hooks, reusable components, routing, and state management in production."
        
        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "React")
        self.assertEqual(res["cv_match_status"], "Match")
        self.assertIn(res["cv_level"], ["intermediate", "advanced"])

    def test_scenario_b_react_intermediate_basic_evidence(self):
        """
        B. Required: React — Intermediate
        CV only says basic/familiar React.
        Expected: Needs Improvement
        """
        requirements = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        cv_text = "Familiar with React."

        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "React")
        self.assertEqual(res["cv_match_status"], "Needs Improvement")
        self.assertEqual(res["cv_level"], "basic")

    def test_scenario_c_javascript_intermediate_no_evidence(self):
        """
        C. Required: JavaScript — Intermediate
        CV has no JavaScript evidence.
        Expected: Missing
        """
        requirements = [{"skill": "JavaScript", "level": "intermediate", "importance": "required"}]
        cv_text = "Experienced in Python and Django backend development."

        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "JavaScript")
        self.assertEqual(res["cv_match_status"], "Missing")
        self.assertEqual(res["cv_level"], "not_found")

    def test_scenario_d_postgresql_intermediate_weak_evidence(self):
        """
        D. Required: PostgreSQL — Intermediate
        CV mentions PostgreSQL but evidence is weak/basic.
        Expected: Needs Improvement
        """
        requirements = [{"skill": "PostgreSQL", "level": "intermediate", "importance": "required"}]
        cv_text = "Used PostgreSQL for simple SELECT queries in a class project."

        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "PostgreSQL")
        self.assertEqual(res["cv_match_status"], "Needs Improvement")
        self.assertEqual(res["cv_level"], "basic")

    def test_scenario_e_python_basic_demonstrated(self):
        """
        E. Required: Python — Basic
        CV demonstrates Python.
        Expected: Match
        """
        requirements = [{"skill": "Python", "level": "basic", "importance": "required"}]
        cv_text = "Wrote Python scripts for data cleaning and automation."

        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "Python")
        self.assertEqual(res["cv_match_status"], "Match")

    def test_scenario_f_git_unspecified_mentioned(self):
        """
        F. Required: Git — Unspecified
        CV mentions Git.
        Expected: Match
        """
        requirements = [{"skill": "Git", "level": "unspecified", "importance": "required"}]
        cv_text = "Used Git for version control and code collaboration."

        results = evaluate_cv_with_gemini(cv_text, requirements)
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertEqual(res["skill"], "Git")
        self.assertEqual(res["cv_match_status"], "Match")

    def test_scenario_g_previous_assessment_does_not_affect_missing_cv_status(self):
        """
        G. A previous Intermediate JavaScript assessment exists in DB,
        but JavaScript is absent from CV.
        Expected: CV Match Status MUST STILL BE 'Missing'.
        """
        attempt = AssessmentAttempt(
            user_id=801,
            skill="JavaScript",
            required_level="intermediate",
            cv_level=None,
            assessed_level="intermediate",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_text = "Experienced in Python and Django backend development."
        eval_result = evaluate_cv_with_gemini(cv_text, [{"skill": "JavaScript", "level": "intermediate", "importance": "required"}])

        score_data = {"score": 0, "matched_count": 0, "missing_count": 1, "total_skills": 1}
        combined = combine_cv_and_assessment({
            "skills": eval_result,
            "matched_skills": [],
            "missing_skills": eval_result,
            "score_data": score_data
        }, db_or_assessments=self.db, user_id=801)

        js_skill = combined["missing_skills"][0]
        self.assertEqual(js_skill["skill"], "JavaScript")
        self.assertEqual(js_skill["cv_match_status"], "Missing")
        self.assertEqual(js_skill["assessed_level"], "intermediate")
        self.assertFalse(js_skill["matched"])

    def test_scenario_h_previous_assessment_does_not_affect_needs_improvement_cv_status(self):
        """
        H. A previous Basic PostgreSQL assessment exists in DB,
        but CV evidence is below Intermediate.
        Expected: CV Match Status MUST STILL BE 'Needs Improvement'.
        """
        attempt = AssessmentAttempt(
            user_id=802,
            skill="PostgreSQL",
            required_level="intermediate",
            cv_level=None,
            assessed_level="basic",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        self.db.commit()

        cv_text = "Basic exposure to PostgreSQL."
        eval_result = evaluate_cv_with_gemini(cv_text, [{"skill": "PostgreSQL", "level": "intermediate", "importance": "required"}])

        score_data = {"score": 0, "matched_count": 0, "missing_count": 1, "total_skills": 1}
        combined = combine_cv_and_assessment({
            "skills": eval_result,
            "matched_skills": [],
            "missing_skills": eval_result,
            "score_data": score_data
        }, db_or_assessments=self.db, user_id=802)

        pg_skill = combined["matched_skills"][0]
        self.assertEqual(pg_skill["skill"], "PostgreSQL")
        self.assertEqual(pg_skill["cv_match_status"], "Needs Improvement")
        self.assertEqual(pg_skill["assessed_level"], "basic")
        self.assertTrue(pg_skill["matched"])


    def test_actionable_feedback_truthful_rewrite(self):
        requirements = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        cv_text = "Built multiple React applications"
        results = evaluate_cv_with_gemini(cv_text, requirements)
        fb = results[0]["actionable_feedback"]
        self.assertIsNotNone(fb)
        self.assertEqual(fb["category"], "safe rewrite")
        self.assertNotIn("hooks", fb["suggested_wording"].lower())
        self.assertNotIn("routing", fb["suggested_wording"].lower())
        self.assertEqual(fb["suggested_wording"], "Engineered multiple React applications.")

    def test_actionable_feedback_clarification_needed(self):
        requirements = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        cv_text = "Familiar with React."
        results = evaluate_cv_with_gemini(cv_text, requirements)
        fb = results[0]["actionable_feedback"]
        self.assertIsNotNone(fb)
        self.assertEqual(fb["category"], "clarification needed")
        self.assertIsNone(fb["suggested_wording"])
        self.assertTrue(len(fb["follow_up_questions"]) > 0)

    def test_actionable_feedback_not_evidenced(self):
        requirements = [{"skill": "JavaScript", "level": "intermediate", "importance": "required"}]
        cv_text = "Experienced in Python and Django backend development."
        results = evaluate_cv_with_gemini(cv_text, requirements)
        fb = results[0]["actionable_feedback"]
        self.assertIsNotNone(fb)
        self.assertEqual(fb["category"], "requirement not evidenced")

    def test_actionable_feedback_evidence_mismatch(self):
        # Python evaluates with original_text "Fake original text not in CV" which doesn't match cv_text
        requirements = [{"skill": "Python", "level": "basic", "importance": "required"}]
        cv_text = "Wrote Python scripts for data cleaning and automation."
        results = evaluate_cv_with_gemini(cv_text, requirements)
        fb = results[0]["actionable_feedback"]
        self.assertIsNotNone(fb)
        # Because of mismatch, it should fall back to clarification needed and clear text/suggestion
        self.assertEqual(fb["category"], "clarification needed")
        self.assertIsNone(fb["original_text"])
        self.assertIsNone(fb["suggested_wording"])

    @patch("openai.OpenAI")
    def test_llm_failure_returns_502(self, mock_openai):
        from fastapi import HTTPException
        requirements = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        cv_text = "Built multiple React applications"
        
        # Configure mock to raise an exception
        mock_client = MagicMock()
        mock_model = MagicMock()
        mock_model.id = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        mock_client.models.list.return_value.data = [mock_model]
        mock_client.chat.completions.create.side_effect = Exception("Simulated API Error")
        mock_openai.return_value = mock_client
        
        # Temporarily switch to Groq provider to test its failure path
        old_provider = os.environ.get("LLM_PROVIDER")
        os.environ["LLM_PROVIDER"] = "groq"
        
        try:
            with self.assertRaises(HTTPException) as context:
                evaluate_cv_with_gemini(cv_text, requirements)
            
            self.assertEqual(context.exception.status_code, 502)
            self.assertIn("CV Evaluation Error", str(context.exception.detail))
        finally:
            if old_provider is not None:
                os.environ["LLM_PROVIDER"] = old_provider
            else:
                del os.environ["LLM_PROVIDER"]

if __name__ == "__main__":
    unittest.main()
