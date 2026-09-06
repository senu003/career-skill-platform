from fastapi import FastAPI
from sqlalchemy import text

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(cv_router)
app.include_router(requirements_router)
app.include_router(assessment_router)
app.include_router(ml_router)
app.include_router(aggregation_router)