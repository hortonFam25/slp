from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.dependencies.access_control import ensure_goal_access, ensure_objective_access
from app.dependencies.auth import AuthContext, get_auth_context
from app.repositories.goal_repository import ObjectiveRepository
from app.services import archive as archive_service
from app.schemas.goal_objective import (
    GoalObjectiveCreate,
    GoalObjectiveRead,
    GoalObjectiveUpdate,
    GoalObjectiveWithProgress
)


router = APIRouter(prefix="/api", tags=["objectives"], dependencies=[Depends(get_auth_context)])


@router.get("/objectives", response_model=List[GoalObjectiveRead])
def get_objectives(
    goal_id: Optional[int] = Query(None, description="Filter by goal ID"),
    progress_status: Optional[str] = Query(None, description="Filter by progress status"),
    schedule_frequency: Optional[str] = Query(None, description="Filter by schedule frequency"),
    include_archived: bool = Query(False, description="Include archived rows (archived means hidden, never deleted)"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get objectives with optional filters"""
    repo = ObjectiveRepository(db)
    if goal_id is not None:
        ensure_goal_access(db, auth, goal_id)
    objectives = repo.get_objectives(
        goal_id=goal_id,
        progress_status=progress_status,
        schedule_frequency=schedule_frequency,
        include_archived=include_archived,
    )
    if auth.enforce_access and not auth.is_admin:
        return [o for o in objectives if o.goal and o.goal.student_id in auth.allowed_student_ids]
    return objectives


@router.get("/objectives/{objective_id}", response_model=GoalObjectiveRead)
def get_objective(
    objective_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific objective by ID"""
    repo = ObjectiveRepository(db)
    objective = repo.get_objective_by_id(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    ensure_objective_access(db, auth, objective_id)
    return objective


@router.get("/objectives/{objective_id}/with-progress", response_model=GoalObjectiveWithProgress)
def get_objective_with_progress(
    objective_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get an objective with all its progress entries"""
    repo = ObjectiveRepository(db)
    objective = repo.get_objective_by_id(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    ensure_objective_access(db, auth, objective_id)
    return objective


@router.get("/goals/{goal_id}/objectives", response_model=List[GoalObjectiveWithProgress])
def get_goal_objectives(
    goal_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all objectives for a specific goal"""
    ensure_goal_access(db, auth, goal_id)
    repo = ObjectiveRepository(db)
    return repo.get_goal_objectives(goal_id)


@router.post("/objectives", response_model=GoalObjectiveRead)
def create_objective(
    objective: GoalObjectiveCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new objective"""
    ensure_goal_access(db, auth, objective.goal_id)
    repo = ObjectiveRepository(db)
    
    # Check if objective number already exists for this goal
    existing_objectives = repo.get_goal_objectives(objective.goal_id)
    existing_numbers = [obj.objective_number for obj in existing_objectives]
    
    if objective.objective_number in existing_numbers:
        raise HTTPException(
            status_code=400, 
            detail=f"Objective number {objective.objective_number} already exists for this goal"
        )
    
    try:
        objective_data = objective.dict()
        return repo.create_objective(objective_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create objective: {str(e)}")


@router.put("/objectives/{objective_id}", response_model=GoalObjectiveRead)
def update_objective(
    objective_id: int, 
    objective_data: GoalObjectiveUpdate, 
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing objective"""
    repo = ObjectiveRepository(db)
    
    # Get the current objective
    current_objective = repo.get_objective_by_id(objective_id)
    if not current_objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    ensure_objective_access(db, auth, objective_id)
    
    # If updating objective number, check for conflicts
    update_dict = objective_data.dict(exclude_unset=True)
    if 'objective_number' in update_dict:
        new_number = update_dict['objective_number']
        existing_objectives = repo.get_goal_objectives(current_objective.goal_id)
        existing_numbers = [
            obj.objective_number for obj in existing_objectives 
            if obj.id != objective_id  # Exclude current objective
        ]
        
        if new_number in existing_numbers:
            raise HTTPException(
                status_code=400, 
                detail=f"Objective number {new_number} already exists for this goal"
            )
    
    objective = repo.update_objective(objective_id, update_dict)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


@router.delete("/objectives/{objective_id}")
def delete_objective(
    objective_id: int,
    reason: Optional[str] = Query(None, description="Why the objective is being archived"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive an objective with its progress entries. NOTHING IS DELETED.

    Same verb, same path, same message. The objective and its entries are
    stamped with one archive event; restore it through
    `POST /api/archive/events/{archiveEventId}/restore`.
    """
    ensure_objective_access(db, auth, objective_id)
    repo = ObjectiveRepository(db)
    if repo.get_objective_by_id(objective_id) is None:
        raise HTTPException(status_code=404, detail="Objective not found")
    try:
        event = archive_service.archive(
            db,
            user_id=auth.effective_user.id,
            entity_type=archive_service.ENTITY_OBJECTIVE,
            entity_id=objective_id,
            reason=reason,
        )
    except archive_service.AlreadyArchivedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "message": "Objective deleted successfully",
        "archived": True,
        "archiveEventId": event.id,
    }
