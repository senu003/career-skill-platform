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


# Ensure tables exist and seed question bank
Base.metadata.create_all(bind=engine)
with SessionLocal() as db_session:
    seed_assessment_questions(db_session)

app = FastAPI(
    title="Career Skill Intelligence Platform"
)

app.include_router(users_router)
app.include_router(cv_router)
app.include_router(requirements_router)
app.include_router(assessment_router)
app.include_router(ml_router)
