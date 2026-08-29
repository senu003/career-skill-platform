import sys
import os
import json
import unittest
from unittest.mock import patch

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCVAnalyzeEndpoint(unittest.TestCase):

    @patch("app.services.cv_service.extract_pdf_text")
    def test_analyze_cv_success(self, mock_extract_pdf_text):
        # Mock extract_pdf_text to return specified CV text
        mock_extract_pdf_text.return_value = {
            "pages": 1,
            "text": "I have experience building REST APIs using Python and FastAPI. I also use Docker."
        }

        requirements = [
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "FastAPI", "level": "intermediate", "importance": "required"},
            {"skill": "Docker", "level": "basic", "importance": "preferred"},
            {"skill": "Kubernetes", "level": "intermediate", "importance": "required"},
        ]

        response = client.post(
            "/cv/analyze",
            files={"file": ("candidate.pdf", b"%PDF-1.4 dummy binary content", "application/pdf")},
            data={"requirements": json.dumps(requirements)}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["filename"], "candidate.pdf")
        self.assertEqual(data["pages"], 1)

        matched_skills = data["matched_skills"]
        missing_skills = data["missing_skills"]

        # Check skill classification
        matched_names = [s["skill"] for s in matched_skills]
        missing_names = [s["skill"] for s in missing_skills]

        self.assertEqual(matched_names, ["Python", "FastAPI", "Docker"])
        self.assertEqual(missing_names, ["Kubernetes"])

        # Verify levels remain JOB REQUIRED LEVELS
        python_item = next(s for s in matched_skills if s["skill"] == "Python")
        self.assertEqual(python_item["level"], "advanced")
        self.assertEqual(python_item["importance"], "required")
        self.assertIn("Python", python_item["evidence"])

        fastapi_item = next(s for s in matched_skills if s["skill"] == "FastAPI")
        self.assertEqual(fastapi_item["level"], "intermediate")
        self.assertEqual(fastapi_item["importance"], "required")

        docker_item = next(s for s in matched_skills if s["skill"] == "Docker")
        self.assertEqual(docker_item["level"], "basic")
        self.assertEqual(docker_item["importance"], "preferred")

        k8s_item = next(s for s in missing_skills if s["skill"] == "Kubernetes")
        self.assertEqual(k8s_item["level"], "intermediate")

        # Verify score_data calculation
        self.assertIn("score_data", data)
        self.assertEqual(data["score_data"]["total_skills"], 4)
        self.assertEqual(data["score_data"]["matched_count"], 3)
        self.assertEqual(data["score_data"]["missing_count"], 1)
        self.assertEqual(data["score_data"]["score"], 75.0)


    def test_validation_invalid_json(self):
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": "invalid { json"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid requirements JSON format", response.json()["detail"])

    def test_validation_not_a_list(self):
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": json.dumps({"skill": "Python", "level": "basic", "importance": "required"})}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Requirements JSON must be a list", response.json()["detail"])

    def test_validation_empty_list(self):
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": "[]"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Requirements list cannot be empty", response.json()["detail"])

    def test_validation_item_not_dict(self):
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": json.dumps(["Python", "FastAPI"])}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("must be an object", response.json()["detail"])

    def test_validation_missing_skill(self):
        reqs = [{"level": "advanced", "importance": "required"}]
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": json.dumps(reqs)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing 'skill'", response.json()["detail"])

    def test_validation_missing_level(self):
        reqs = [{"skill": "Python", "importance": "required"}]
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": json.dumps(reqs)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing 'level'", response.json()["detail"])

    def test_validation_missing_importance(self):
        reqs = [{"skill": "Python", "level": "advanced"}]
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            data={"requirements": json.dumps(reqs)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing 'importance'", response.json()["detail"])

    def test_validation_non_pdf_upload(self):
        reqs = [{"skill": "Python", "level": "advanced", "importance": "required"}]
        response = client.post(
            "/cv/analyze",
            files={"file": ("test.txt", b"plain text content", "text/plain")},
            data={"requirements": json.dumps(reqs)}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only PDF files are allowed", response.json()["detail"])

    @patch("app.services.cv_service.extract_pdf_text")
    def test_analyze_cv_with_assessment_integration(self, mock_extract_pdf_text):
        from app.database import SessionLocal
        from app.models import AssessmentAttempt
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            attempt = AssessmentAttempt(
                user_id=888,
                skill="Python",
                required_level="advanced",
                cv_level=None,
                assessed_level="intermediate",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc)
            )
            db.add(attempt)
            db.commit()
        finally:
            db.close()

        mock_extract_pdf_text.return_value = {
            "pages": 1,
            "text": "I am proficient in Python and React."
        }

        requirements = [
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "Docker", "level": "basic", "importance": "required"}
        ]

        response = client.post(
            "/cv/analyze",
            files={"file": ("cv.pdf", b"%PDF-1.4 test", "application/pdf")},
            data={"requirements": json.dumps(requirements), "user_id": 888}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("skills", data)
        python_skill = next(s for s in data["skills"] if s["skill"] == "Python")
        self.assertEqual(python_skill["matched"], True)
        self.assertIsNone(python_skill["cv_level"])
        self.assertEqual(python_skill["assessed_level"], "intermediate")
        self.assertEqual(python_skill["level_gap"], 1)

        docker_skill = next(s for s in data["skills"] if s["skill"] == "Docker")
        self.assertEqual(docker_skill["matched"], False)
        self.assertIsNone(docker_skill["cv_level"])
        self.assertIsNone(docker_skill["assessed_level"])
        self.assertIsNone(docker_skill["level_gap"])
        self.assertIsNone(docker_skill["evidence"])


if __name__ == "__main__":
    unittest.main()

