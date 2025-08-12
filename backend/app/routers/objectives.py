from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.repositories.goal_repository import ObjectiveRepository
from app.schemas.goal_objective import (
    GoalObjectiveCreate,
    GoalObjectiveRead,
    GoalObjectiveUpdate,
    GoalObjectiveWithProgress
)


router = APIRouter(prefix="/api", tags=["objectives"])


@router.get("/objectives", response_model=List[GoalObjectiveRead])
def get_objectives(
    goal_id: Optional[int] = Query(None, description="Filter by goal ID"),
    progress_status: Optional[str] = Query(None, description="Filter by progress status"),
    schedule_frequency: Optional[str] = Query(None, description="Filter by schedule frequency"),
    db: Session = Depends(get_db)
):
    """Get objectives with optional filters"""
    repo = ObjectiveRepository(db)
    return repo.get_objectives(
        goal_id=goal_id,
        progress_status=progress_status,
        schedule_frequency=schedule_frequency
    )


@router.get("/objectives/{objective_id}", response_model=GoalObjectiveRead)
def get_objective(objective_id: int, db: Session = Depends(get_db)):
    """Get a specific objective by ID"""
    repo = ObjectiveRepository(db)
    objective = repo.get_objective_by_id(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


@router.get("/objectives/{objective_id}/with-progress", response_model=GoalObjectiveWithProgress)
def get_objective_with_progress(objective_id: int, db: Session = Depends(get_db)):
    """Get an objective with all its progress entries"""
    repo = ObjectiveRepository(db)
    objective = repo.get_objective_by_id(objective_id)
    if not objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    return objective


@router.get("/goals/{goal_id}/objectives", response_model=List[GoalObjectiveWithProgress])
def get_goal_objectives(goal_id: int, db: Session = Depends(get_db)):
    """Get all objectives for a specific goal"""
    repo = ObjectiveRepository(db)
    return repo.get_goal_objectives(goal_id)


@router.post("/objectives", response_model=GoalObjectiveRead)
def create_objective(objective: GoalObjectiveCreate, db: Session = Depends(get_db)):
    """Create a new objective"""
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
    db: Session = Depends(get_db)
):
    """Update an existing objective"""
    repo = ObjectiveRepository(db)
    
    # Get the current objective
    current_objective = repo.get_objective_by_id(objective_id)
    if not current_objective:
        raise HTTPException(status_code=404, detail="Objective not found")
    
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
def delete_objective(objective_id: int, db: Session = Depends(get_db)):
    """Delete an objective and all related progress entries"""
    repo = ObjectiveRepository(db)
    success = repo.delete_objective(objective_id)
    if not success:
        raise HTTPException(status_code=404, detail="Objective not found")
    return {"message": "Objective deleted successfully"}
