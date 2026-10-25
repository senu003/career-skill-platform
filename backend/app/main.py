import os
import logging
from dotenv import load_dotenv

backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if os.path.exists(backend_env):
    load_dotenv(backend_env, override=True)
else:
    load_dotenv(override=True)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
from .database import engine, SessionLocal, Base
from . import models
from .services.seed_questions import seed_assessment_questions
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.cv import router as cv_router
from .routers.requirements import router as requirements_router
from .routers.assessment import router as assessment_router
from .routers.ml import router as ml_router
from .routers.aggregation import router as aggregation_router

# Schema initialization:
# In production, migrations must be executed explicitly via Alembic before starting application workers.
# RUN_RUNTIME_DDL is disabled by default (0) to eliminate concurrent DDL lock contention.
RUN_RUNTIME_DDL = os.getenv("RUN_RUNTIME_DDL", "0").lower() in ("1", "true", "yes")

if RUN_RUNTIME_DDL:
    logger.info("RUN_RUNTIME_DDL enabled — executing fallback DDL checks...")
    Base.metadata.create_all(bind=engine)

    _COLUMN_MIGRATIONS = [
        "ALTER TABLE assessment_questions ADD COLUMN IF NOT EXISTS question_type VARCHAR(50) DEFAULT 'MCQ'",
        "ALTER TABLE assessment_answers ADD COLUMN IF NOT EXISTS time_taken NUMERIC(8, 2)",
        "ALTER TABLE assessment_attempts ADD COLUMN IF NOT EXISTS analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
        "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",
    ]

    try:
        with engine.connect() as conn:
            for ddl in _COLUMN_MIGRATIONS:
                try:
                    conn.execute(text(ddl))
                except Exception as col_err:
                    logger.debug(f"Column migration skipped (likely already applied): {col_err}")
            conn.commit()
    except Exception as migrate_err:
        logger.warning(f"Schema migration step failed — continuing: {migrate_err}")
else:
    logger.info("RUN_RUNTIME_DDL is disabled — schema managed by external Alembic migrations.")

SEED_ON_STARTUP = os.getenv("SEED_ON_STARTUP", "0").lower() in ("1", "true", "yes")
if SEED_ON_STARTUP:
    with SessionLocal() as db_session:
        seed_assessment_questions(db_session)

from fastapi.middleware.cors import CORSMiddleware
from app.rate_limiter import limiter, RateLimitExceeded, SlowAPIMiddleware

app = FastAPI(
    title="Career Skill Intelligence Platform",
    description="AI-powered career & skill gap analysis platform",
    version="2.0.0",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

frontend_origins_str = os.getenv("FRONTEND_ORIGINS", "")
frontend_origins = [origin.strip() for origin in frontend_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins if frontend_origins else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Please slow down your requests."},
        headers={"Retry-After": str(retry_after)}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (HTTPException, RateLimitExceeded)):
        raise exc
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# New versioned auth routes (recommended)
app.include_router(auth_router)

# Legacy routes kept for backward compat with existing frontend calls
app.include_router(users_router)
app.include_router(cv_router)
app.include_router(requirements_router)
app.include_router(assessment_router)
app.include_router(ml_router)
app.include_router(aggregation_router)
