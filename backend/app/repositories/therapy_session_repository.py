from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, or_
from app.models.therapy_session import TherapySession
from app.models.session_goal import SessionGoal
from app.models.session_objective import SessionObjective
from app.models.appointment import Appointment
from app.models.student import Student
from app.models.iep_goal import IEPGoal
from app.models.goal_objective import GoalObjective
from app.schemas.therapy_session import (
    TherapySessionCreate, TherapySessionUpdate, TherapySessionFilters,
    SessionGoalCreate, SessionObjectiveCreate,
    StartSessionRequest, CompleteSessionRequest
)


class TherapySessionRepository:
    """Repository for managing therapy sessions and related data"""

    def __init__(self, db: Session):
        self.db = db

    def get_session_by_appointment_id(self, appointment_id: int) -> Optional[TherapySession]:
        """Get therapy session by appointment ID with goals and objectives loaded"""
        return self.db.query(TherapySession)\
            .options(
                selectinload(TherapySession.session_goals).joinedload(SessionGoal.goal),
                selectinload(TherapySession.session_objectives).joinedload(SessionObjective.objective)
            )\
            .filter(TherapySession.appointment_id == appointment_id)\
            .first()

    def create_session(self, session_data: TherapySessionCreate) -> TherapySession:
        """Create a new therapy session with optional goals and objectives"""
        
        # Create the main therapy session
        session = TherapySession(
            student_id=session_data.student_id,
            appointment_id=session_data.appointment_id,
            time_block_id=session_data.time_block_id,
            session_date=session_data.session_date,
            start_time=session_data.start_time,
            end_time=session_data.end_time,
            planned_duration_minutes=session_data.planned_duration_minutes,
            actual_duration_minutes=session_data.actual_duration_minutes,
            session_type=session_data.session_type,
            status=session_data.status,
            created_from=session_data.created_from,
            prep_notes=session_data.prep_notes,
            session_notes=session_data.session_notes,
            therapist_observations=session_data.therapist_observations,
            student_engagement=session_data.student_engagement,
            materials_used=session_data.materials_used,
            goals_addressed=session_data.goals_addressed,
            session_quality=session_data.session_quality,
            follow_up_needed=session_data.follow_up_needed,
            follow_up_notes=session_data.follow_up_notes
        )
        
        self.db.add(session)
        self.db.flush()  # Get the session ID
        
        # Add planned goals
        for goal_data in session_data.planned_goals or []:
            session_goal = SessionGoal(
                therapy_session_id=session.id,
                goal_id=goal_data.goal_id,
                planned=goal_data.planned,
                priority=goal_data.priority,
                pre_session_notes=goal_data.pre_session_notes
            )
            self.db.add(session_goal)
        
        # Add planned objectives
        for objective_data in session_data.planned_objectives or []:
            session_objective = SessionObjective(
                therapy_session_id=session.id,
                objective_id=objective_data.objective_id,
                goal_id=objective_data.goal_id,
                planned=objective_data.planned,
                priority=objective_data.priority,
                pre_session_notes=objective_data.pre_session_notes
            )
            self.db.add(session_objective)
        
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session_by_id(self, session_id: int, include_details: bool = False) -> Optional[TherapySession]:
        """Get a therapy session by ID with optional related data"""
        query = self.db.query(TherapySession).filter(TherapySession.id == session_id)
        
        if include_details:
            query = query.options(
                selectinload(TherapySession.session_goals).joinedload(SessionGoal.goal),
                selectinload(TherapySession.session_objectives).joinedload(SessionObjective.objective),
                joinedload(TherapySession.student),
                joinedload(TherapySession.appointment),
                joinedload(TherapySession.time_block)
            )
        
        return query.first()

    def get_sessions(self, filters: TherapySessionFilters, skip: int = 0, limit: int = 100, order_by: str = "desc") -> List[TherapySession]:
        """Get therapy sessions with filtering and pagination"""
        query = self.db.query(TherapySession).join(Student)
        
        # Apply filters
        if filters.student_id:
            query = query.filter(TherapySession.student_id == filters.student_id)
        
        if filters.appointment_id:
            query = query.filter(TherapySession.appointment_id == filters.appointment_id)
        
        if filters.time_block_id:
            query = query.filter(TherapySession.time_block_id == filters.time_block_id)
        
        if filters.session_type:
            query = query.filter(TherapySession.session_type == filters.session_type)
        
        if filters.status:
            query = query.filter(TherapySession.status == filters.status)
        
        if filters.created_from:
            query = query.filter(TherapySession.created_from == filters.created_from)
        
        if filters.start_date:
            # SQL Server compatible date comparison
            start_datetime = datetime.combine(filters.start_date, datetime.min.time())
            query = query.filter(TherapySession.session_date >= start_datetime)
        
        if filters.end_date:
            # SQL Server compatible date comparison
            end_datetime = datetime.combine(filters.end_date, datetime.max.time())
            query = query.filter(TherapySession.session_date <= end_datetime)
        
        if filters.session_quality:
            query = query.filter(TherapySession.session_quality == filters.session_quality)
        
        if filters.goals_addressed is not None:
            query = query.filter(TherapySession.goals_addressed == filters.goals_addressed)
        
        if filters.follow_up_needed is not None:
            query = query.filter(TherapySession.follow_up_needed == filters.follow_up_needed)
        
        # Include related data if requested
        if filters.include_goals:
            query = query.options(selectinload(TherapySession.session_goals))
        
        if filters.include_objectives:
            query = query.options(selectinload(TherapySession.session_objectives))
        
        # Always include student for name
        query = query.options(joinedload(TherapySession.student))
        
        # Order by session date based on order_by parameter
        if order_by.lower() == "asc":
            query = query.order_by(TherapySession.session_date.asc())
        else:
            query = query.order_by(TherapySession.session_date.desc())
        
        return query.offset(skip).limit(limit).all()

    def get_school_year_sessions_relative(
        self,
        student_id: int,
        start_date: date,
        end_date: date,
        anchor_date: date,
        limit: int = 75,
        include_goals: bool = False,
        include_objectives: bool = False,
    ) -> List[TherapySession]:
        """Get a window of school-year sessions centered around an anchor date."""
        query = self.db.query(TherapySession).join(Student).filter(
            TherapySession.student_id == student_id
        )

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(
            TherapySession.session_date >= start_datetime,
            TherapySession.session_date <= end_datetime,
        )

        if include_goals:
            query = query.options(selectinload(TherapySession.session_goals))

        if include_objectives:
            query = query.options(selectinload(TherapySession.session_objectives))

        query = query.options(joinedload(TherapySession.student))

        sessions = query.order_by(TherapySession.session_date.asc()).all()
        if len(sessions) <= limit:
            return sessions

        anchor_index = next(
            (index for index, session in enumerate(sessions) if session.session_date.date() == anchor_date),
            None,
        )

        if anchor_index is None:
            anchor_end = datetime.combine(anchor_date, datetime.max.time())
            anchor_index = max(
                0,
                sum(1 for session in sessions if session.session_date <= anchor_end) - 1,
            )

        half_window = limit // 2
        window_start = max(0, anchor_index - half_window)
        max_window_start = max(0, len(sessions) - limit)
        window_start = min(window_start, max_window_start)

        return sessions[window_start:window_start + limit]

    def update_session(self, session_id: int, session_data: TherapySessionUpdate) -> Optional[TherapySession]:
        """Update an existing therapy session"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None
        
        # Update fields that are provided
        update_data = session_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)
        
        # Update modified date
        session.modified_date = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: int) -> bool:
        """Delete a therapy session and all related data"""
        session = self.get_session_by_id(session_id)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True

    def update_session_objective(self, session_id: int, objective_id: int, objective_data: 'SessionObjectiveUpdate') -> Optional['SessionObjective']:
        """Update a specific session objective, creating it if it doesn't exist"""
        from app.models.session_objective import SessionObjective
        from app.models.goal_objective import GoalObjective
        
        # Find the session objective
        session_objective = self.db.query(SessionObjective).filter(
            SessionObjective.therapy_session_id == session_id,
            SessionObjective.objective_id == objective_id
        ).first()
        
        # If it doesn't exist, create it
        if not session_objective:
            # Get the goal_id from the objective
            goal_objective = self.db.query(GoalObjective).filter(
                GoalObjective.id == objective_id
            ).first()
            
            if not goal_objective:
                return None  # Objective doesn't exist
            
            # Create new session objective
            session_objective = SessionObjective(
                therapy_session_id=session_id,
                objective_id=objective_id,
                goal_id=goal_objective.goal_id,
                planned=False,  # Default to False since we're creating it during the session
                worked_on=True, # Set to True since we're updating progress
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            )
            self.db.add(session_objective)
        
        # Update fields that are provided
        update_data = objective_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session_objective, field, value)
        
        # Ensure worked_on is True when we're updating progress
        session_objective.worked_on = True
        
        # Update modified date
        session_objective.modified_date = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(session_objective)
        return session_objective

    def get_objective_history(self, objective_id: int) -> List['SessionObjective']:
        """Get historical session data for a specific objective"""
        from app.models.session_objective import SessionObjective
        from app.models.therapy_session import TherapySession
        
        session_objectives = self.db.query(SessionObjective)\
            .join(TherapySession, SessionObjective.therapy_session_id == TherapySession.id)\
            .filter(
                SessionObjective.objective_id == objective_id,
                SessionObjective.worked_on == True,
                TherapySession.status == 'completed'
            )\
            .order_by(TherapySession.session_date.desc())\
            .limit(10)\
            .all()
        
        # Manually load therapy_session relationship for each session_objective
        for session_obj in session_objectives:
            if not session_obj.therapy_session:
                session_obj.therapy_session = self.db.query(TherapySession)\
                    .filter(TherapySession.id == session_obj.therapy_session_id)\
                    .first()
        
        return session_objectives

    def get_goal_history(self, goal_id: int) -> dict:
        """Get historical session data for all objectives under a goal"""
        from app.models.session_objective import SessionObjective
        from app.models.therapy_session import TherapySession
        from app.models.goal_objective import GoalObjective
        from app.models.iep_goal import IEPGoal
        
        # Get goal info
        goal = self.db.query(IEPGoal).filter(IEPGoal.id == goal_id).first()
        
        # Get historical sessions for all objectives under this goal
        sessions = self.db.query(SessionObjective)\
            .join(TherapySession, SessionObjective.therapy_session_id == TherapySession.id)\
            .join(GoalObjective, SessionObjective.objective_id == GoalObjective.id)\
            .filter(
                GoalObjective.goal_id == goal_id,
                SessionObjective.worked_on == True,
                TherapySession.status == 'completed'
            )\
            .order_by(TherapySession.session_date.desc())\
            .limit(20)\
            .all()
        
        # Manually load therapy_session relationship for each session_objective
        for session_obj in sessions:
            if not session_obj.therapy_session:
                session_obj.therapy_session = self.db.query(TherapySession)\
                    .filter(TherapySession.id == session_obj.therapy_session_id)\
                    .first()
        
        return {
            "sessions": sessions,
            "goal_info": {
                "id": goal.id if goal else None,
                "goal_number": goal.goal_number if goal else None,
                "description": goal.goal_description if goal else None,
                "category": goal.goal_category.name if goal and goal.goal_category else None
            }
        }

    def start_session(self, request: StartSessionRequest) -> TherapySession:
        """Start a new therapy session based on request type"""
        
        # If starting from an existing appointment, find the existing therapy session (regardless of status)
        if request.appointment_id and request.session_type == 'link_existing':
            existing_session = self.db.query(TherapySession).filter(
                TherapySession.appointment_id == request.appointment_id
            ).first()
            
            if existing_session:
                # Use the existing session and update its status to in_progress if needed
                if existing_session.status != "in_progress":
                    existing_session.status = "in_progress"
                # Always set actual start time when starting a session
                existing_session.actual_start_time = datetime.now()
                if request.prep_notes:
                    existing_session.prep_notes = request.prep_notes
                
                self.db.commit()
                self.db.refresh(existing_session)
                return existing_session
        
        # Optionally create an appointment for unscheduled sessions (intended pattern)
        appointment_id: Optional[int] = request.appointment_id
        scheduled_start: Optional[datetime] = None
        scheduled_end: Optional[datetime] = None
        if request.create_appointment and not appointment_id:
            now = datetime.now()
            duration_minutes = request.planned_duration_minutes or 30
            appointment = Appointment(
                student_id=request.student_id,
                start_datetime=now,
                end_datetime=now + timedelta(minutes=duration_minutes),
                appointment_type="individual",
                status="in_progress",
                therapy_session_completed=False,
                notes="Auto-created from unscheduled therapy session"
            )
            self.db.add(appointment)
            self.db.flush()  # Get appointment ID
            appointment_id = appointment.id
            scheduled_start = appointment.start_datetime
            scheduled_end = appointment.end_datetime

        # Otherwise create a new session
        session_data = TherapySessionCreate(
            student_id=request.student_id,
            appointment_id=appointment_id,
            session_date=datetime.now(),
            actual_start_time=datetime.now(),
            # If we auto-created an appointment, store scheduled window to match it
            start_time=scheduled_start,
            end_time=scheduled_end,
            planned_duration_minutes=request.planned_duration_minutes,
            session_type=request.session_type,
            status="in_progress",
            created_from="manual" if request.session_type == "unscheduled" else "appointment",
            prep_notes=request.prep_notes
        )
        
        # Add planned goals
        planned_goals = []
        if request.planned_goals:
            for goal_id in request.planned_goals:
                planned_goals.append(SessionGoalCreate(goal_id=goal_id, planned=True))
        session_data.planned_goals = planned_goals
        
        # Add planned objectives  
        planned_objectives = []
        
        # Handle objectives with notes (preferred method)
        if request.planned_objectives_with_notes:
            for obj_data in request.planned_objectives_with_notes:
                planned_objectives.append(SessionObjectiveCreate(
                    objective_id=obj_data.objective_id,
                    goal_id=obj_data.goal_id,
                    planned=True,
                    priority=obj_data.priority,
                    pre_session_notes=obj_data.pre_session_notes
                ))
        
        # Handle basic objective IDs (fallback for compatibility)
        elif request.planned_objectives:
            for objective_id in request.planned_objectives:
                # Get the goal_id for this objective
                objective = self.db.query(GoalObjective).filter(GoalObjective.id == objective_id).first()
                if objective:
                    planned_objectives.append(SessionObjectiveCreate(
                        objective_id=objective_id,
                        goal_id=objective.goal_id,
                        planned=True
                    ))
        
        session_data.planned_objectives = planned_objectives
        
        return self.create_session(session_data)

    def complete_session(self, session_id: int, request: CompleteSessionRequest) -> Optional[TherapySession]:
        """Complete a therapy session"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None
        
        # Update session with completion data
        session.actual_end_time = datetime.now()
        session.status = "completed"
        session.session_notes = request.session_notes
        session.therapist_observations = request.therapist_observations
        session.student_engagement = request.student_engagement
        session.materials_used = request.materials_used
        session.goals_addressed = request.goals_addressed
        session.session_quality = request.session_quality
        session.follow_up_needed = request.follow_up_needed
        session.follow_up_notes = request.follow_up_notes
        
        # Calculate actual duration
        if not session.actual_start_time:
            # Defensive fallback for legacy sessions to avoid inflated durations
            session.actual_start_time = datetime.now()
        if session.actual_start_time and session.actual_end_time:
            duration = session.actual_end_time - session.actual_start_time
            session.actual_duration_minutes = int(duration.total_seconds() / 60)
        
        # Update linked appointment if exists
        if session.appointment:
            session.appointment.therapy_session_completed = True
            session.appointment.session_notes = request.session_notes
            session.appointment.status = "completed"
        
        session.modified_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_student_sessions(self, student_id: int, limit: int = 50) -> List[TherapySession]:
        """Get recent therapy sessions for a specific student"""
        return self.db.query(TherapySession)\
            .filter(TherapySession.student_id == student_id)\
            .order_by(TherapySession.session_date.desc())\
            .limit(limit)\
            .all()

    def get_active_sessions(self) -> List[TherapySession]:
        """Get all currently active (in-progress) therapy sessions"""
        return self.db.query(TherapySession)\
            .filter(TherapySession.status == "in_progress")\
            .options(joinedload(TherapySession.student))\
            .order_by(TherapySession.start_time.asc())\
            .all()

    def get_sessions_needing_followup(self) -> List[TherapySession]:
        """Get completed sessions that need follow-up"""
        return self.db.query(TherapySession)\
            .filter(
                and_(
                    TherapySession.status == "completed",
                    TherapySession.follow_up_needed == True
                )
            )\
            .options(joinedload(TherapySession.student))\
            .order_by(TherapySession.session_date.desc())\
            .all()

    def get_session_statistics(self, student_id: Optional[int] = None, 
                              start_date: Optional[date] = None,
                              end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get statistical summary of therapy sessions"""
        query = self.db.query(TherapySession)
        
        if student_id:
            query = query.filter(TherapySession.student_id == student_id)
        
        if start_date:
            query = query.filter(func.date(TherapySession.session_date) >= start_date)
        
        if end_date:
            query = query.filter(func.date(TherapySession.session_date) <= end_date)
        
        sessions = query.all()
        
        if not sessions:
            return {
                "total_sessions": 0,
                "completed_sessions": 0,
                "cancelled_sessions": 0,
                "average_duration": 0,
                "goals_addressed_rate": 0,
                "session_quality_breakdown": {}
            }
        
        completed_sessions = [s for s in sessions if s.status == "completed"]
        cancelled_sessions = [s for s in sessions if s.status == "cancelled"]
        goals_addressed_sessions = [s for s in completed_sessions if s.goals_addressed]
        
        # Calculate average duration for completed sessions
        durations = [s.duration_minutes for s in completed_sessions if s.duration_minutes > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Session quality breakdown
        quality_breakdown = {}
        for session in completed_sessions:
            if session.session_quality:
                quality_breakdown[session.session_quality] = quality_breakdown.get(session.session_quality, 0) + 1
        
        return {
            "total_sessions": len(sessions),
            "completed_sessions": len(completed_sessions),
            "cancelled_sessions": len(cancelled_sessions),
            "average_duration": round(avg_duration, 1),
            "goals_addressed_rate": round(len(goals_addressed_sessions) / len(completed_sessions) * 100, 1) if completed_sessions else 0,
            "session_quality_breakdown": quality_breakdown
        }
