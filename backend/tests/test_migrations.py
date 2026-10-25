import os
import sys
import unittest
from pathlib import Path
from sqlalchemy import create_engine, inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic import command
from scripts.run_migrations import run_database_migrations


class TestDatabaseMigrations(unittest.TestCase):

    def setUp(self):
        self.backend_dir = Path(__file__).resolve().parent.parent
        self.ini_path = self.backend_dir / "alembic.ini"
        self.script_dir = self.backend_dir / "alembic"

    def test_alembic_configuration_and_scripts_exist(self):
        self.assertTrue(self.ini_path.exists(), "alembic.ini must exist")
        self.assertTrue(self.script_dir.exists(), "alembic/ directory must exist")
        self.assertTrue((self.script_dir / "env.py").exists(), "alembic/env.py must exist")
        self.assertTrue((self.script_dir / "versions" / "001_initial_schema.py").exists(), "Initial migration must exist")

    def test_migration_runner_executes_successfully(self):
        success = run_database_migrations()
        self.assertTrue(success, "run_database_migrations must return True")

    def test_fresh_database_setup_path(self):
        """Verifies migration can build all tables cleanly from scratch on a blank database."""
        import tempfile
        temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db_file.close()
        temp_db_path = temp_db_file.name
        sqlite_url = f"sqlite:///{temp_db_path}"

        alembic_cfg = Config(str(self.ini_path))
        alembic_cfg.set_main_option("script_location", str(self.script_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)

        try:
            # Upgrade blank database to head
            command.upgrade(alembic_cfg, "head")

            # Inspect created tables
            test_engine = create_engine(sqlite_url)
            inspector = inspect(test_engine)
            tables = inspector.get_table_names()

            required_tables = [
                "users", "cvs", "jobs", "analyses",
                "assessment_questions", "assessment_attempts", "assessment_answers",
                "password_reset_tokens", "security_audit_logs"
            ]
            for t in required_tables:
                self.assertIn(t, tables, f"Expected table {t} to be created on fresh database setup")
        finally:
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
