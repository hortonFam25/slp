from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.settings import settings
from app.routers import health, students, csv_import, goals, objectives, progress_entries, schools, teachers, scheduling, therapy_sessions, eligibilities, goals_import
from app.db import database

app = FastAPI(title="SLP Pro API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/health", tags=["health"]) 
app.include_router(students.router)
app.include_router(csv_import.router)
app.include_router(goals_import.router)
app.include_router(goals.router)
app.include_router(objectives.router)
app.include_router(progress_entries.router)
app.include_router(schools.router)
app.include_router(teachers.router)
app.include_router(scheduling.router)
app.include_router(therapy_sessions.router)
app.include_router(eligibilities.router)


@app.on_event("startup")
def on_startup():
    # Ensure tables exist for local dev (migrations in prod)
    from app.db.base import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=database.engine)

@app.get("/")
def root():
    return {"name": "slppro", "status": "ok"}


