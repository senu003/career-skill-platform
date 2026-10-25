"""
DATABASE MIGRATION RUNNER SCRIPT

Executes Alembic migrations prior to application worker startup.
Ensures zero-downtime, idempotent schema synchronization without
concurrent DDL race conditions.
"""

import os
import sys
import time
import logging

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_runner")


def wait_for_database(db_url: str, max_retries: int = 15, delay: float = 2.0) -> bool:
    """Waits for database to be ready and accept connections."""
    engine = create_engine(db_url)
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connectivity confirmed.")
            return True
        except Exception as e:
            logger.warning(f"Database not ready (attempt {attempt}/{max_retries}): {e}")
            time.sleep(delay)
    return False


def run_database_migrations(database_url: str = None) -> bool:
    """Runs Alembic migrations up to head. Returns True on success, False on failure."""
    if not database_url:
        database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required.")
        return False

    logger.info("Verifying database connectivity...")
    if not wait_for_database(database_url):
        logger.error("Unable to connect to database. Aborting migrations.")
        return False

    ini_path = os.path.join(backend_dir, "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    logger.info("Executing Alembic migration upgrade head...")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations successfully applied up to head.")
    except Exception as e:
        logger.error(f"Migration execution failed: {e}")
        return False

    # Seed assessment question bank if empty
    try:
        from app.database import SessionLocal
        from app.models import AssessmentQuestion
        from app.services.seed_questions import seed_assessment_questions

        with SessionLocal() as db_session:
            count = db_session.query(AssessmentQuestion).count()
            if count == 0:
                logger.info("Assessment questions bank is empty. Seeding initial questions...")
                seed_assessment_questions(db_session)
                logger.info("Question bank seeded successfully.")
            else:
                logger.info(f"Question bank already populated ({count} questions). Skipping seeding.")
    except Exception as seed_err:
        logger.warning(f"Seeding check failed (non-critical): {seed_err}")

    return True


def run_migrations():
    """CLI entrypoint for executing migrations."""
    success = run_database_migrations()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()
