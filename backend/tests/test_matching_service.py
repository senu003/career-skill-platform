import sys
import os
import unittest

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.matching_service import match_skills_in_text, build_skill_regex, get_skill_variants


class TestSkillMatchingService(unittest.TestCase):

    def test_example_from_specification(self):
        cv_text = "I have experience building REST APIs using Python and FastAPI. I also use Docker."
        required_skills = [
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "FastAPI", "level": "intermediate", "importance": "required"},
            {"skill": "Docker", "level": "basic", "importance": "required"},
            {"skill": "Kubernetes", "level": "unspecified", "importance": "required"},
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)

        matched_names = [m["skill"] for m in matched]
        missing_names = [m["skill"] for m in missing]

        self.assertEqual(matched_names, ["Python", "FastAPI", "Docker"])
        self.assertEqual(missing_names, ["Kubernetes"])

        # Check preserved fields and evidence
        for item in matched:
            self.assertIn("level", item)
            self.assertIn("importance", item)
            self.assertIn("evidence", item)
            self.assertTrue(len(item["evidence"]) > 0)

        for item in missing:
            self.assertIn("level", item)
            self.assertIn("importance", item)
            self.assertNotIn("evidence", item)

    def test_alias_matching(self):
        # CV uses canonical/alternative names, required skills use short aliases or variants
        cv_text = "Experienced software engineer specializing in JavaScript, React.js, and PostgreSQL database administration. Deployed on Kubernetes."

        required_skills = [
            {"skill": "JS", "level": "advanced", "importance": "required"},
            {"skill": "React", "level": "intermediate", "importance": "required"},
            {"skill": "Postgres", "level": "intermediate", "importance": "required"},
            {"skill": "K8s", "level": "basic", "importance": "preferred"},
            {"skill": "Vue", "level": "basic", "importance": "preferred"},
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)

        matched_names = [m["skill"] for m in matched]
        missing_names = [m["skill"] for m in missing]

        self.assertEqual(matched_names, ["JS", "React", "Postgres", "K8s"])
        self.assertEqual(missing_names, ["Vue"])

    def test_word_boundary_java_vs_javascript(self):
        cv_text = "I am a full-stack developer with extensive experience in JavaScript and TypeScript."
        required_skills = [
            {"skill": "Java", "level": "advanced", "importance": "required"},
            {"skill": "JavaScript", "level": "advanced", "importance": "required"},
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)

        matched_names = [m["skill"] for m in matched]
        missing_names = [m["skill"] for m in missing]

        self.assertNotIn("Java", matched_names)
        self.assertIn("Java", missing_names)
        self.assertIn("JavaScript", matched_names)

    def test_word_boundary_c_vs_general_text_and_cpp(self):
        cv_text = "I have 5 years of experience in C++ and C# development across cloud platforms."
        required_skills = [
            {"skill": "C", "level": "advanced", "importance": "required"},
            {"skill": "C++", "level": "advanced", "importance": "required"},
            {"skill": "C#", "level": "advanced", "importance": "required"},
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)

        matched_names = [m["skill"] for m in matched]
        missing_names = [m["skill"] for m in missing]

        # 'C' should NOT match 'experience' or 'C++' or 'C#'
        self.assertNotIn("C", matched_names)
        self.assertIn("C", missing_names)
        self.assertIn("C++", matched_names)
        self.assertIn("C#", matched_names)

    def test_word_boundary_c_standalone(self):
        cv_text = "Proficient in C programming and embedded systems."
        required_skills = [
            {"skill": "C", "level": "advanced", "importance": "required"}
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)
        matched_names = [m["skill"] for m in matched]

        self.assertIn("C", matched_names)

    def test_case_insensitive_matching(self):
        cv_text = "worked with DOCKER, python, and FASTAPI."
        required_skills = [
            {"skill": "docker", "level": "basic", "importance": "required"},
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "FastApi", "level": "intermediate", "importance": "required"},
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)
        matched_names = [m["skill"] for m in matched]

        self.assertEqual(len(matched), 3)
        self.assertEqual(len(missing), 0)

    def test_empty_inputs(self):
        cv_text = ""
        required_skills = [
            {"skill": "Python", "level": "advanced", "importance": "required"}
        ]

        matched, missing = match_skills_in_text(cv_text, required_skills)
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(missing), 1)

        matched_empty, missing_empty = match_skills_in_text("Some text", [])
        self.assertEqual(len(matched_empty), 0)
        self.assertEqual(len(missing_empty), 0)


if __name__ == "__main__":
    unittest.main()
