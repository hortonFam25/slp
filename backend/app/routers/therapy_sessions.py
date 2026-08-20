from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.dependencies.access_control import (
    ensure_appointment_access,
    ensure_goal_access,
    ensure_objective_access,
    ensure_therapy_session_access,
)
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.repositories.therapy_session_repository import TherapySessionRepository
from app.services import archive as archive_service
from app.schemas.therapy_session import (
    TherapySessionCreate, TherapySessionUpdate, TherapySessionResponse, 
    TherapySessionSummary, TherapySessionFilters,
    StartSessionRequest, CompleteSessionRequest,
    SessionGoalResponse, SessionObjectiveResponse, SessionObjectiveUpdate
)

router = APIRouter(prefix="/api/therapy-sessions", tags=["therapy-sessions"], dependencies=[Depends(get_auth_context)])


def get_therapy_session_repo(db: Session = Depends(get_db)) -> TherapySessionRepository:
    return TherapySessionRepository(db)


def _should_mask_student_names(auth: AuthContext) -> bool:
    return auth.is_admin or auth.user.id != auth.effective_user.id


def _student_alias_from_session(session) -> str | None:
    if not session or not session.student:
        return None
    return session.student.student_alias or f"student_{session.student.id}"


def _student_name_for_session(session, auth: AuthContext) -> str | None:
    if not session or not session.student:
        return None
    if _should_mask_student_names(auth):
        return _student_alias_from_session(session)
    return session.student.full_name


@router.post("/", response_model=TherapySessionResponse)
@router.post("", response_model=TherapySessionResponse)  # Handle both with and without trailing slash
async def create_therapy_session(
    session_data: TherapySessionCreate,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new therapy session with optional goals and objectives"""
    try:
        ensure_student_access(auth, session_data.student_id, action="create therapy session")
        session = repo.create_session(session_data)
        return _build_session_response(session, auth)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create therapy session: {str(e)}")


@router.post("/start", response_model=TherapySessionResponse)
async def start_therapy_session(
    request: StartSessionRequest,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Start a new therapy session (scheduled, unscheduled, or ad-hoc)"""
    try:
        ensure_student_access(auth, request.student_id, action="start therapy session")
        session = repo.start_session(request)
        return _build_session_response(session, auth)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start therapy session: {str(e)}")


@router.get("/by-appointment/{appointment_id}")
async def get_therapy_session_by_appointment(
    appointment_id: int,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get therapy session with goals and objectives by appointment ID"""
    try:
        ensure_appointment_access(repo.db, auth, appointment_id)
        session = repo.get_session_by_appointment_id(appointment_id)
        if not session:
            # Return empty data instead of 404 - appointment exists but no session data yet
            return {
                "goals": [],
                "objectives": []
            }
        
        # Build response with goals and objectives
        goals = []
        for session_goal in session.session_goals:
            goals.append({
                "goal_id": session_goal.goal_id,
                "goal_text": session_goal.goal.goal_description,
                "planned": session_goal.planned,
                "worked_on": session_goal.worked_on
            })
        
        objectives = []
        for session_objective in session.session_objectives:
            objectives.append({
                "objective_id": session_objective.objective_id,
                "goal_id": session_objective.goal_id,
                "objective_text": session_objective.objective.objective_description,
                "planned": session_objective.planned,
                "worked_on": session_objective.worked_on,
                "pre_session_notes": session_objective.pre_session_notes
            })
        
        return {
            "goals": goals,
            "objectives": objectives
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load therapy session: {str(e)}")


@router.put("/by-appointment/{appointment_id}/objectives")
async def update_therapy_session_objectives_by_appointment(
    appointment_id: int,
    request: dict,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update therapy session objectives with pre-session notes for an existing appointment session"""
    try:
        ensure_appointment_access(repo.db, auth, appointment_id)
        # Get the therapy session for this appointment
        session = repo.get_session_by_appointment_id(appointment_id)
        
        # Session must already exist - we don't create sessions from this endpoint
        if not session:
            raise HTTPException(
                status_code=404, 
                detail="No therapy session found for this appointment. Please create a session first from the therapy interface."
            )
        
        objectives_data = request.get("objectives", [])
        
        # Update or create session objectives using the repository's database session
        from app.models.session_objective import SessionObjective
        
        for obj_data in objectives_data:
            # Validate required fields
            if "objective_id" not in obj_data or "goal_id" not in obj_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required fields: objective_id and goal_id must be provided"
                )
            
            objective_id = obj_data["objective_id"]
            goal_id = obj_data["goal_id"]
            
            # Validate that the objective exists and belongs to the specified goal
            from app.models.goal_objective import GoalObjective
            from app.models.iep_goal import IEPGoal
            
            goal_objective = repo.db.query(GoalObjective).filter(
                GoalObjective.id == objective_id,
                GoalObjective.goal_id == goal_id
            ).first()
            
            if not goal_objective:
                raise HTTPException(
                    status_code=400,
                    detail=f"Objective {objective_id} not found or doesn't belong to goal {goal_id}"
                )
            
            # Check if session objective already exists
            existing_objective = repo.db.query(SessionObjective).filter(
                SessionObjective.therapy_session_id == session.id,
                SessionObjective.objective_id == objective_id
            ).first()
            
            if existing_objective:
                # Update existing objective
                existing_objective.pre_session_notes = obj_data.get("pre_session_notes")
                existing_objective.planned = obj_data.get("planned", True)
                existing_objective.priority = obj_data.get("priority", 1)
                existing_objective.modified_date = datetime.utcnow()
            else:
                # Create new session objective
                new_objective = SessionObjective(
                    therapy_session_id=session.id,
                    objective_id=objective_id,
                    goal_id=goal_id,
                    planned=obj_data.get("planned", True),
                    worked_on=False,
                    priority=obj_data.get("priority", 1),
                    pre_session_notes=obj_data.get("pre_session_notes"),
                    created_date=datetime.utcnow(),
                    modified_date=datetime.utcnow()
                )
                repo.db.add(new_objective)
        
        repo.db.commit()
        
        return {"message": "Therapy session objectives updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update therapy session objectives: {str(e)}")


@router.get("/", response_model=List[TherapySessionSummary])
@router.get("", response_model=List[TherapySessionSummary])  # Handle both with and without trailing slash
async def get_therapy_sessions(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    session_type: Optional[str] = Query(None, description="Filter by session type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    order_by: Optional[str] = Query("desc", description="Order direction: 'asc' for oldest first, 'desc' for newest first"),
    include_archived: bool = Query(False, description="Include archived rows (archived means hidden, never deleted)"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    if student_id is not None:
        ensure_student_access(auth, student_id, action="list therapy sessions")
    """Get therapy sessions with optional filtering"""
    filters = TherapySessionFilters(
        student_id=student_id,
        session_type=session_type,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    sessions = repo.get_sessions(
        filters, skip=skip, limit=limit, order_by=order_by, include_archived=include_archived
    )
    if auth.enforce_access and not auth.is_admin:
        sessions = [s for s in sessions if s.student_id in auth.allowed_student_ids]
    return [_build_session_summary(session, auth) for session in sessions]


@router.get("/{session_id}", response_model=TherapySessionResponse)
async def get_therapy_session(
    session_id: int,
    include_details: bool = Query(True, description="Include goals and objectives"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific therapy session by ID"""
    session = repo.get_session_by_id(session_id, include_details=include_details)
    if not session:
        raise HTTPException(status_code=404, detail="Therapy session not found")
    ensure_therapy_session_access(repo.db, auth, session_id)
    
    return _build_session_response(session, auth)


@router.put("/{session_id}", response_model=TherapySessionResponse)
async def update_therapy_session(
    session_id: int,
    session_data: TherapySessionUpdate,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an existing therapy session"""
    ensure_therapy_session_access(repo.db, auth, session_id)
    session = repo.update_session(session_id, session_data)
    if not session:
        raise HTTPException(status_code=404, detail="Therapy session not found")
    
    return _build_session_response(session, auth)


@router.post("/{session_id}/complete", response_model=TherapySessionResponse)
async def complete_therapy_session(
    session_id: int,
    request: CompleteSessionRequest,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Complete a therapy session"""
    ensure_therapy_session_access(repo.db, auth, session_id)
    session = repo.complete_session(session_id, request)
    if not session:
        raise HTTPException(status_code=404, detail="Therapy session not found")
    
    return _build_session_response(session, auth)


@router.put("/{session_id}/objectives/{objective_id}", response_model=SessionObjectiveResponse)
async def update_session_objective(
    session_id: int,
    objective_id: int,
    objective_data: SessionObjectiveUpdate,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update a session objective's progress data"""
    ensure_therapy_session_access(repo.db, auth, session_id)
    session_objective = repo.update_session_objective(session_id, objective_id, objective_data)
    if not session_objective:
        raise HTTPException(status_code=404, detail="Session objective not found")
    
    return session_objective

@router.get("/objectives/{objective_id}/history", response_model=List[SessionObjectiveResponse])
async def get_objective_history(
    objective_id: int,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get historical session data for a specific objective"""
    ensure_objective_access(repo.db, auth, objective_id)
    return repo.get_objective_history(objective_id)

@router.get("/goals/{goal_id}/history")
async def get_goal_history(
    goal_id: int,
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get historical session data for all objectives under a goal"""
    ensure_goal_access(repo.db, auth, goal_id)
    return repo.get_goal_history(goal_id)


@router.delete("/{session_id}")
async def delete_therapy_session(
    session_id: int,
    reason: Optional[str] = Query(None, description="Why the session is being archived"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive one therapy session. NOTHING IS DELETED.

    Same verb, same path, same message. The session is hidden and
    `POST /api/archive/events/{archiveEventId}/restore` brings it back.

    Its PROGRESS ENTRIES are deliberately left active: they belong to an
    objective, they are the evidence a service was delivered, and the old delete
    took them with it only because a foreign-key cascade said so. See
    `app/services/archive.py`.
    """
    ensure_therapy_session_access(repo.db, auth, session_id)
    if repo.get_session_by_id(session_id) is None:
        raise HTTPException(status_code=404, detail="Therapy session not found")
    try:
        event = archive_service.archive(
            repo.db,
            user_id=auth.effective_user.id,
            entity_type=archive_service.ENTITY_THERAPY_SESSION,
            entity_id=session_id,
            reason=reason,
        )
    except archive_service.AlreadyArchivedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "message": "Therapy session deleted successfully",
        "archived": True,
        "archiveEventId": event.id,
    }


@router.get("/student/{student_id}", response_model=List[TherapySessionSummary])
async def get_student_therapy_sessions(
    student_id: int,
    limit: int = Query(50, ge=1, le=200, description="Number of recent sessions to return"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get recent therapy sessions for a specific student"""
    ensure_student_access(auth, student_id, action="student therapy sessions")
    sessions = repo.get_student_sessions(student_id, limit=limit)
    return [_build_session_summary(session, auth) for session in sessions]


@router.get("/student/{student_id}/school-year", response_model=List[TherapySessionResponse])
async def get_student_school_year_sessions(
    student_id: int,
    start_date: date = Query(..., description="School year start date (typically August 1)"),
    end_date: date = Query(..., description="School year end date (typically June 30)"),
    anchor_date: Optional[date] = Query(None, description="Date to center the returned session window around"),
    limit: int = Query(75, ge=1, le=75, description="Maximum number of sessions to return"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get therapy sessions for a student within a school year date range"""
    ensure_student_access(auth, student_id, action="student school year sessions")
    sessions = repo.get_school_year_sessions_relative(
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
        anchor_date=anchor_date or date.today(),
        limit=limit,
        include_objectives=True,
        include_goals=True,
    )
    return [_build_session_response(session, auth) for session in sessions]


@router.get("/active/all", response_model=List[TherapySessionSummary])
async def get_active_therapy_sessions(
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all currently active (in-progress) therapy sessions"""
    sessions = repo.get_active_sessions()
    if auth.enforce_access and not auth.is_admin:
        sessions = [s for s in sessions if s.student_id in auth.allowed_student_ids]
    return [_build_session_summary(session, auth) for session in sessions]


@router.get("/followup/needed", response_model=List[TherapySessionSummary])
async def get_sessions_needing_followup(
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get completed sessions that need follow-up"""
    sessions = repo.get_sessions_needing_followup()
    if auth.enforce_access and not auth.is_admin:
        sessions = [s for s in sessions if s.student_id in auth.allowed_student_ids]
    return [_build_session_summary(session, auth) for session in sessions]


@router.get("/statistics/summary")
async def get_therapy_session_statistics(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    repo: TherapySessionRepository = Depends(get_therapy_session_repo),
    auth: AuthContext = Depends(get_auth_context),
):
    if student_id is not None:
        ensure_student_access(auth, student_id, action="therapy statistics")
    """Get statistical summary of therapy sessions"""
    return repo.get_session_statistics(
        student_id=student_id,
        start_date=start_date,
        end_date=end_date
    )


# Helper functions to build response objects
def _build_session_response(session, auth: AuthContext) -> TherapySessionResponse:
    """Build a complete therapy session response"""
    response_data = {
        "id": session.id,
        "student_id": session.student_id,
        "appointment_id": session.appointment_id,
        "time_block_id": session.time_block_id,
        "session_date": session.session_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "actual_start_time": session.actual_start_time,
        "actual_end_time": session.actual_end_time,
        "planned_duration_minutes": session.planned_duration_minutes,
        "actual_duration_minutes": session.actual_duration_minutes,
        "session_type": session.session_type,
        "status": session.status,
        "created_from": session.created_from,
        "prep_notes": session.prep_notes,
        "session_notes": session.session_notes,
        "therapist_observations": session.therapist_observations,
        "student_engagement": session.student_engagement,
        "materials_used": session.materials_used,
        "goals_addressed": session.goals_addressed,
        "session_quality": session.session_quality,
        "follow_up_needed": session.follow_up_needed,
        "follow_up_notes": session.follow_up_notes,
        "created_date": session.created_date,
        "modified_date": session.modified_date,
        "created_by": session.created_by,
        
        # Computed properties
        "duration_minutes": session.duration_minutes,
        "is_scheduled": session.is_scheduled,
        "is_group_session": session.is_group_session,
        "is_active": session.is_active,
        "is_completed": session.is_completed,
        
        # Counts
        "planned_goals_count": session.planned_goals_count,
        "worked_goals_count": session.worked_goals_count,
        "planned_objectives_count": session.planned_objectives_count,
        "worked_objectives_count": session.worked_objectives_count,
        "progress_entries_count": session.progress_entries_count,
        
        # Student name
        "student_name": _student_name_for_session(session, auth),
    }
    
    # Include session goals if loaded
    if hasattr(session, 'session_goals') and session.session_goals:
        response_data["session_goals"] = [
            SessionGoalResponse(
                id=sg.id,
                therapy_session_id=sg.therapy_session_id,
                goal_id=sg.goal_id,
                planned=sg.planned,
                worked_on=sg.worked_on,
                priority=sg.priority,
                pre_session_notes=sg.pre_session_notes,
                session_notes=sg.session_notes,
                goal_progress_summary=sg.goal_progress_summary,
                goal_met=sg.goal_met,
                difficulty_level=sg.difficulty_level,
                student_response=sg.student_response,
                time_spent_minutes=sg.time_spent_minutes,
                created_date=sg.created_date,
                modified_date=sg.modified_date,
                goal_description=sg.goal.goal_description if sg.goal else None,
                goal_category=sg.goal.goal_category.name if sg.goal and sg.goal.goal_category else None
            )
            for sg in session.session_goals
        ]
    
    # Include session objectives if loaded
    if hasattr(session, 'session_objectives') and session.session_objectives:
        response_data["session_objectives"] = [
            SessionObjectiveResponse(
                id=so.id,
                therapy_session_id=so.therapy_session_id,
                objective_id=so.objective_id,
                goal_id=so.goal_id,
                planned=so.planned,
                worked_on=so.worked_on,
                priority=so.priority,
                pre_session_notes=so.pre_session_notes,
                session_notes=so.session_notes,
                trials_attempted=so.trials_attempted,
                trials_correct=so.trials_correct,
                accuracy_percentage=so.accuracy_percentage,
                independence_level=so.independence_level,
                objective_met=so.objective_met,
                progress_rating=so.progress_rating,
                prompt_level=so.prompt_level,
                time_spent_minutes=so.time_spent_minutes,
                student_engagement=so.student_engagement,
                data_collection_method=so.data_collection_method,
                created_date=so.created_date,
                modified_date=so.modified_date,
                objective_description=so.objective.objective_description if so.objective else None,
                goal_description=so.goal.goal_description if so.goal else None,
                success_rate=so.success_rate
            )
            for so in session.session_objectives
        ]
    
    return TherapySessionResponse(**response_data)


def _build_session_summary(session, auth: AuthContext) -> TherapySessionSummary:
    """Build a lightweight therapy session summary"""
    return TherapySessionSummary(
        id=session.id,
        student_id=session.student_id,
        student_name=_student_name_for_session(session, auth),
        session_date=session.session_date,
        start_time=session.start_time,
        end_time=session.end_time,
        actual_start_time=session.actual_start_time,
        actual_end_time=session.actual_end_time,
        duration_minutes=session.duration_minutes,
        session_type=session.session_type,
        status=session.status,
        is_scheduled=session.is_scheduled,
        goals_addressed=session.goals_addressed,
        session_quality=session.session_quality,
        created_date=session.created_date
    )
