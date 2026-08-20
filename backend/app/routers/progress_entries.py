from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.dependencies.access_control import ensure_objective_access, ensure_progress_entry_access
from app.dependencies.auth import AuthContext, get_auth_context
from app.repositories.goal_repository import ProgressEntryRepository
from app.schemas.goal_objective import (
    ObjectiveProgressEntryCreate,
    ObjectiveProgressEntryRead,
    ObjectiveProgressEntryUpdate
)


router = APIRouter(prefix="/api", tags=["progress-entries"], dependencies=[Depends(get_auth_context)])


@router.get("/progress-entries", response_model=List[ObjectiveProgressEntryRead])
def get_progress_entries(
    objective_id: Optional[int] = Query(None, description="Filter by objective ID"),
    progress_date_from: Optional[date] = Query(None, description="Filter entries from this date"),
    progress_date_to: Optional[date] = Query(None, description="Filter entries to this date"),
    therapist_initials: Optional[str] = Query(None, description="Filter by therapist initials"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get progress entries with optional filters"""
    if objective_id is not None:
        ensure_objective_access(db, auth, objective_id)
    repo = ProgressEntryRepository(db)
    entries = repo.get_progress_entries(
        objective_id=objective_id,
        progress_date_from=progress_date_from,
        progress_date_to=progress_date_to,
        therapist_initials=therapist_initials
    )
    if auth.enforce_access and not auth.is_admin:
        return [e for e in entries if e.objective and e.objective.goal and e.objective.goal.student_id in auth.allowed_student_ids]
    return entries


@router.get("/progress-entries/{entry_id}", response_model=ObjectiveProgressEntryRead)
def get_progress_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific progress entry by ID"""
    repo = ProgressEntryRepository(db)
    entry = repo.get_progress_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Progress entry not found")
    ensure_progress_entry_access(db, auth, entry_id)
    return entry


@router.get("/objectives/{objective_id}/progress-entries", response_model=List[ObjectiveProgressEntryRead])
def get_objective_progress_entries(
    objective_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all progress entries for a specific objective"""
    ensure_objective_access(db, auth, objective_id)
    repo = ProgressEntryRepository(db)
    return repo.get_objective_progress_entries(objective_id)


@router.post("/progress-entries", response_model=ObjectiveProgressEntryRead)
def create_progress_entry(
    entry: ObjectiveProgressEntryCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new progress entry"""
    ensure_objective_access(db, auth, entry.objective_id)
    repo = ProgressEntryRepository(db)
    
    try:
        entry_data = entry.dict()
        return repo.create_progress_entry(entry_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create progress entry: {str(e)}")


@router.put("/progress-entries/{entry_id}", response_model=ObjectiveProgressEntryRead)
def update_progress_entry(
    entry_id: int, 
    entry_data: ObjectiveProgressEntryUpdate, 
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing progress entry"""
    ensure_progress_entry_access(db, auth, entry_id)
    repo = ProgressEntryRepository(db)
    
    update_dict = entry_data.dict(exclude_unset=True)
    entry = repo.update_progress_entry(entry_id, update_dict)
    if not entry:
        raise HTTPException(status_code=404, detail="Progress entry not found")
    return entry


@router.delete("/progress-entries/{entry_id}")
def delete_progress_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete a progress entry"""
    ensure_progress_entry_access(db, auth, entry_id)
    repo = ProgressEntryRepository(db)
    success = repo.delete_progress_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Progress entry not found")
    return {"message": "Progress entry deleted successfully"}


@router.get("/objectives/{objective_id}/latest-progress", response_model=ObjectiveProgressEntryRead)
def get_latest_progress_entry(
    objective_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get the most recent progress entry for an objective"""
    ensure_objective_access(db, auth, objective_id)
    repo = ProgressEntryRepository(db)
    entry = repo.get_latest_entry_for_objective(objective_id)
    if not entry:
        raise HTTPException(status_code=404, detail="No progress entries found for this objective")
    return entry
