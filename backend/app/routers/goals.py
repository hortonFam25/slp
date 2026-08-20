from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.dependencies.access_control import ensure_goal_access
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.repositories.goal_repository import GoalRepository
from app.repositories.goal_category_repository import GoalCategoryRepository
from app.services import archive as archive_service
from app.schemas.iep_goal import IEPGoalCreate, IEPGoalRead, IEPGoalUpdate, IEPGoalWithObjectives, IEPGoalSummary
from app.schemas.goal_category import GoalCategoryRead, GoalCategoryCreate, GoalCategoryUpdate


router = APIRouter(prefix="/api", tags=["goals"], dependencies=[Depends(get_auth_context)])


# Goal Categories Endpoints
@router.get("/goal-categories", response_model=List[GoalCategoryRead])
def get_goal_categories(
    active_only: bool = Query(False, description="Filter to only active categories"),
    db: Session = Depends(get_db)
):
    """Get all goal categories from the goal_categories table"""
    repo = GoalCategoryRepository(db)
    return repo.get_all_categories(active_only=active_only)


@router.get("/goal-categories/{category_id}", response_model=GoalCategoryRead)
def get_goal_category(category_id: int, db: Session = Depends(get_db)):
    """Get a specific goal category by ID"""
    repo = GoalCategoryRepository(db)
    category = repo.get_category_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Goal category not found")
    return category


@router.post("/goal-categories", response_model=GoalCategoryRead)
def create_goal_category(category_data: GoalCategoryCreate, db: Session = Depends(get_db)):
    """Create a new goal category"""
    repo = GoalCategoryRepository(db)
    try:
        return repo.create_category(category_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create category: {str(e)}")


@router.put("/goal-categories/{category_id}", response_model=GoalCategoryRead)
def update_goal_category(category_id: int, category_data: GoalCategoryUpdate, db: Session = Depends(get_db)):
    """Update an existing goal category"""
    repo = GoalCategoryRepository(db)
    try:
        updated_category = repo.update_category(category_id, category_data)
        if not updated_category:
            raise HTTPException(status_code=404, detail="Goal category not found")
        return updated_category
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update category: {str(e)}")


@router.delete("/goal-categories/{category_id}")
def delete_goal_category(category_id: int, db: Session = Depends(get_db)):
    """Delete a goal category (only if not in use)"""
    repo = GoalCategoryRepository(db)
    try:
        success = repo.delete_category(category_id)
        if not success:
            raise HTTPException(status_code=404, detail="Goal category not found")
        return {"message": "Goal category deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")


# IEP Goals Endpoints
@router.get("/goals", response_model=List[IEPGoalRead])
def get_goals(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    goal_status: Optional[str] = Query(None, description="Filter by goal status"),
    goal_category_id: Optional[int] = Query(None, description="Filter by goal category"),
    start_date_from: Optional[date] = Query(None, description="Filter goals starting from this date"),
    start_date_to: Optional[date] = Query(None, description="Filter goals starting before this date"),
    include_archived: bool = Query(False, description="Include archived rows (archived means hidden, never deleted)"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get goals with optional filters"""
    repo = GoalRepository(db)
    if student_id is not None:
        ensure_student_access(auth, student_id, action="list goals by student")
    goals = repo.get_goals(
        student_id=student_id,
        goal_status=goal_status,
        goal_category_id=goal_category_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        include_archived=include_archived,
    )
    if auth.enforce_access and not auth.is_admin:
        return [g for g in goals if g.student_id in auth.allowed_student_ids]
    return goals


@router.get("/goals/{goal_id}", response_model=IEPGoalRead)
def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific goal by ID"""
    repo = GoalRepository(db)
    goal = repo.get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    ensure_goal_access(db, auth, goal_id)
    return goal


@router.get("/goals/{goal_id}/with-objectives", response_model=IEPGoalWithObjectives)
def get_goal_with_objectives(
    goal_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a goal with all its objectives and progress entries"""
    repo = GoalRepository(db)
    goal = repo.get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    ensure_goal_access(db, auth, goal_id)
    return goal


@router.get("/students/{student_id}/goals", response_model=List[IEPGoalWithObjectives])
def get_student_goals(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all goals for a specific student"""
    ensure_student_access(auth, student_id, action="list student goals")
    repo = GoalRepository(db)
    return repo.get_student_goals(student_id)


@router.get("/students/{student_id}/goals/active", response_model=List[IEPGoalWithObjectives])
def get_student_active_goals_for_session_planning(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get active goals and their objectives for session planning"""
    ensure_student_access(auth, student_id, action="list active student goals")
    repo = GoalRepository(db)
    # Get only active goals for therapy session planning
    active_goals = repo.get_goals(student_id=student_id, goal_status='Active')
    
    # Get full goal details with objectives for each goal
    detailed_goals = []
    for goal in active_goals:
        detailed_goal = repo.get_goal_with_objectives(goal.id)
        if detailed_goal:
            detailed_goals.append(detailed_goal)
    
    return detailed_goals


@router.get("/students/{student_id}/goals/summary", response_model=List[IEPGoalSummary])
def get_student_goals_summary(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a summary of goals for a specific student"""
    ensure_student_access(auth, student_id, action="list student goal summary")
    repo = GoalRepository(db)
    goals = repo.get_student_goals(student_id)
    
    # Convert to summary format
    summaries = []
    for goal in goals:
        summary = IEPGoalSummary(
            id=goal.id,
            goal_number=goal.goal_number,
            goal_description=goal.goal_description,
            goal_status=goal.goal_status,
            start_date=goal.start_date,
            end_date=goal.end_date,
            mastery_date=goal.mastery_date,
            goal_category_name=goal.goal_category.name if goal.goal_category else None,
            objectives_count=len(goal.objectives) if goal.objectives else 0
        )
        summaries.append(summary)
    
    return summaries


@router.post("/goals", response_model=IEPGoalRead)
def create_goal(
    goal: IEPGoalCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new IEP goal"""
    ensure_student_access(auth, goal.student_id, action="create goal")
    repo = GoalRepository(db)
    try:
        return repo.create_goal(goal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create goal: {str(e)}")


@router.put("/goals/{goal_id}", response_model=IEPGoalRead)
def update_goal(
    goal_id: int,
    goal_data: IEPGoalUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing goal"""
    ensure_goal_access(db, auth, goal_id)
    repo = GoalRepository(db)
    goal = repo.update_goal(goal_id, goal_data)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.delete("/goals/{goal_id}")
def delete_goal(
    goal_id: int,
    reason: Optional[str] = Query(None, description="Why the goal is being archived"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive a goal with its objectives and progress entries. NOTHING IS DELETED.

    Same verb, same path, same message the React app reads. The goal and
    everything under it are stamped with one archive event and hidden;
    `POST /api/archive/events/{archiveEventId}/restore` brings them back.

    Objectives already archived under an EARLIER event are left with that
    event -- restoring this one will not resurrect work that was retired before.
    """
    ensure_goal_access(db, auth, goal_id)
    repo = GoalRepository(db)
    if repo.get_goal_by_id(goal_id) is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    try:
        event = archive_service.archive(
            db,
            user_id=auth.effective_user.id,
            entity_type=archive_service.ENTITY_GOAL,
            entity_id=goal_id,
            reason=reason,
        )
    except archive_service.AlreadyArchivedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "message": "Goal deleted successfully",
        "archived": True,
        "archiveEventId": event.id,
    }


@router.post("/goals/with-objectives", response_model=IEPGoalWithObjectives)
def create_goal_with_objectives(
    goal_data: dict,  # This would need a proper schema for the combined structure
    db: Session = Depends(get_db)
):
    """Create a goal with its objectives in one operation"""
    repo = GoalRepository(db)
    # This would need implementation for creating goal + objectives atomically
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/goals/{goal_id}/duplicate", response_model=IEPGoalRead)
def duplicate_goal(
    goal_id: int,
    target_student_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Duplicate a goal, optionally for a different student"""
    repo = GoalRepository(db)
    # This would need implementation for duplicating goals
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Goals by status
@router.get("/goals/status/{status}", response_model=List[IEPGoalRead])
def get_goals_by_status(
    status: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all goals with a specific status"""
    repo = GoalRepository(db)
    goals = repo.get_goals_by_status(status)
    if auth.enforce_access and not auth.is_admin:
        return [g for g in goals if g.student_id in auth.allowed_student_ids]
    return goals


# Overdue goals
@router.get("/goals/overdue", response_model=List[IEPGoalRead])
def get_overdue_goals(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get goals that are past their end date but still active"""
    repo = GoalRepository(db)
    goals = repo.get_overdue_goals()
    if auth.enforce_access and not auth.is_admin:
        return [g for g in goals if g.student_id in auth.allowed_student_ids]
    return goals


# Progress reporting
@router.get("/goals/{goal_id}/progress-report")
def get_goal_progress_report(
    goal_id: int,
    date_from: Optional[date] = Query(None, description="Start date for progress report"),
    date_to: Optional[date] = Query(None, description="End date for progress report"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a progress report for a specific goal"""
    repo = GoalRepository(db)
    goal = repo.get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    ensure_goal_access(db, auth, goal_id)
    
    # This would need implementation for generating progress reports
    return {
        "goal_id": goal_id,
        "goal_description": goal.goal_description,
        "objectives_count": len(goal.objectives) if goal.objectives else 0,
        "total_progress_entries": sum(
            len(obj.progress_entries) if obj.progress_entries else 0 
            for obj in goal.objectives or []
        ),
        "message": "Detailed progress reporting coming soon"
    }


@router.get("/students/{student_id}/goal-progress")
def get_student_goal_progress(
    student_id: int,
    date_from: Optional[date] = Query(None, description="Start date for progress report"),
    date_to: Optional[date] = Query(None, description="End date for progress report"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get progress report for all goals of a specific student"""
    ensure_student_access(auth, student_id, action="student goal progress")
    repo = GoalRepository(db)
    goals = repo.get_student_goals(student_id)
    
    return {
        "student_id": student_id,
        "goals_count": len(goals),
        "active_goals": len([g for g in goals if g.goal_status == 'Active']),
        "mastered_goals": len([g for g in goals if g.goal_status == 'Mastered']),
        "total_objectives": sum(len(g.objectives) if g.objectives else 0 for g in goals),
        "message": "Detailed student progress reporting coming soon"
    }
