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
from .routers.users import router as users_router
from .routers.cv import router as cv_router
from .routers.requirements import router as requirements_router
from .routers.assessment import router as assessment_router
from .routers.ml import router as ml_router

from .routers.aggregation import router as aggregation_router

# Ensure tables exist and seed question bank
Base.metadata.create_all(bind=engine)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE assessment_questions ADD COLUMN IF NOT EXISTS question_type VARCHAR(50) DEFAULT 'MCQ'"))
        conn.execute(text("ALTER TABLE assessment_answers ADD COLUMN IF NOT EXISTS time_taken NUMERIC(8, 2)"))
        conn.commit()
except Exception:
    pass

with SessionLocal() as db_session:
    seed_assessment_questions(db_session)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Career Skill Intelligence Platform"
)

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
    return {"status": "ok"}

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Re-raise HTTPException so FastAPI handles it with the correct status code.
    # Without this, a 502 raised inside a route would be caught here and returned as 500.
    if isinstance(exc, HTTPException):
        raise exc
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

app.include_router(users_router)
app.include_router(cv_router)
app.include_router(requirements_router)
app.include_router(assessment_router)
app.include_router(ml_router)
app.include_router(aggregation_router)