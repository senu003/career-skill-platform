import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


class TestDatabaseMigrations(unittest.TestCase):

    def setUp(self):
        # Create a fresh temporary SQLite file to simulate a fresh database
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        self.db_url = f"sqlite:///{self.temp_db_path}"

        self.backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.ini_path = os.path.join(self.backend_dir, "alembic.ini")
        self.alembic_cfg = Config(self.ini_path)
        self.alembic_cfg.set_main_option("sqlalchemy.url", self.db_url)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_fresh_database_upgrade_head_creates_all_tables(self):
        # 1. Run upgrade head on fresh database
        command.upgrade(self.alembic_cfg, "head")

        engine = create_engine(self.db_url)
        insp = inspect(engine)
        tables = set(insp.get_table_names())

        expected_tables = {
            "users",
            "password_reset_tokens",
            "security_audit_logs",
            "cvs",
            "skills",
            "cv_skills",
            "jobs",
            "job_skills",
            "questions",
            "assessments",
            "answers",
            "analyses",
            "skill_analyses",
            "recommendations",
            "assessment_questions",
            "question_options",
            "assessment_attempts",
            "assessment_answers",
            "alembic_version",
        }

        for expected in expected_tables:
            self.assertIn(expected, tables, f"Expected table '{expected}' not found in migrated database")

        # Verify key columns exist in users
        user_cols = {c["name"] for c in insp.get_columns("users")}
        self.assertIn("avatar_url", user_cols)
        self.assertIn("oauth_provider", user_cols)
        self.assertIn("oauth_id", user_cols)
        self.assertIn("is_active", user_cols)

    def test_idempotent_upgrade_on_existing_database(self):
        # First upgrade
        command.upgrade(self.alembic_cfg, "head")
        # Second upgrade on the same database should succeed cleanly without crashing or duplicate table errors
        command.upgrade(self.alembic_cfg, "head")

        engine = create_engine(self.db_url)
        insp = inspect(engine)
        self.assertTrue(insp.has_table("users"))

    def test_downgrade_and_reupgrade(self):
        command.upgrade(self.alembic_cfg, "head")
        engine = create_engine(self.db_url)
        insp = inspect(engine)
        self.assertTrue(insp.has_table("users"))

        # Downgrade to base
        command.downgrade(self.alembic_cfg, "base")
        insp_down = inspect(engine)
        self.assertFalse(insp_down.has_table("users"))

        # Re-upgrade to head
        command.upgrade(self.alembic_cfg, "head")
        insp_reup = inspect(engine)
        self.assertTrue(insp_reup.has_table("users"))


if __name__ == "__main__":
    unittest.main()
