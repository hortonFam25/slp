from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field
from decimal import Decimal


class SessionGoalBase(BaseModel):
    goal_id: int = Field(..., description="ID of the IEP goal")
    planned: bool = Field(True, description="Goal was planned for this session")
    worked_on: bool = Field(False, description="Goal was actually addressed in session")
    priority: Optional[int] = Field(None, description="Priority order for this session (1=highest)")
    pre_session_notes: Optional[str] = Field(None, description="Notes before session about this goal")
    session_notes: Optional[str] = Field(None, description="Notes during/after session about this goal")
    goal_progress_summary: Optional[str] = Field(None, description="Summary of progress made on this goal")
    goal_met: Optional[bool] = Field(None, description="Whether goal criteria was met in this session")
    difficulty_level: Optional[str] = Field(None, description="easy, appropriate, challenging, too_difficult")
    student_response: Optional[str] = Field(None, description="engaged, resistant, confused, motivated")
    time_spent_minutes: Optional[int] = Field(None, description="Time spent on this specific goal")


class SessionGoalCreate(SessionGoalBase):
    pass


class SessionGoalUpdate(BaseModel):
    planned: Optional[bool] = None
    worked_on: Optional[bool] = None
    priority: Optional[int] = None
    pre_session_notes: Optional[str] = None
    session_notes: Optional[str] = None
    goal_progress_summary: Optional[str] = None
    goal_met: Optional[bool] = None
    difficulty_level: Optional[str] = None
    student_response: Optional[str] = None
    time_spent_minutes: Optional[int] = None


class SessionGoalResponse(SessionGoalBase):
    id: int
    therapy_session_id: int
    created_date: datetime
    modified_date: datetime
    
    # Include goal details
    goal_description: Optional[str] = None
    goal_category: Optional[str] = None

    class Config:
        from_attributes = True


class SessionObjectiveBase(BaseModel):
    objective_id: int = Field(..., description="ID of the goal objective")
    goal_id: int = Field(..., description="ID of the parent goal")
    planned: bool = Field(True, description="Objective was planned for this session")
    worked_on: bool = Field(False, description="Objective was actually addressed in session")
    priority: Optional[int] = Field(None, description="Priority order for this session (1=highest)")
    pre_session_notes: Optional[str] = Field(None, description="Notes before session about this objective")
    session_notes: Optional[str] = Field(None, description="Notes during/after session about this objective")
    trials_attempted: Optional[int] = Field(None, description="Number of trials attempted")
    trials_correct: Optional[int] = Field(None, description="Number of correct responses")
    accuracy_percentage: Optional[Decimal] = Field(None, description="Calculated accuracy percentage")
    independence_level: Optional[str] = Field(None, description="independent, minimal_cues, moderate_cues, maximum_cues")
    objective_met: Optional[bool] = Field(None, description="Whether objective criteria was met")
    progress_rating: Optional[str] = Field(None, description="no_progress, minimal, moderate, significant, mastered")
    prompt_level: Optional[str] = Field(None, description="none, verbal, visual, physical, hand_over_hand")
    time_spent_minutes: Optional[int] = Field(None, description="Time spent on this specific objective")
    student_engagement: Optional[str] = Field(None, description="high, medium, low")
    data_collection_method: Optional[str] = Field(None, description="How data was collected for this objective")


class SessionObjectiveCreate(SessionObjectiveBase):
    pass


class SessionObjectiveUpdate(BaseModel):
    planned: Optional[bool] = None
    worked_on: Optional[bool] = None
    priority: Optional[int] = None
    pre_session_notes: Optional[str] = None
    session_notes: Optional[str] = None
    trials_attempted: Optional[int] = None
    trials_correct: Optional[int] = None
    accuracy_percentage: Optional[Decimal] = None
    independence_level: Optional[str] = None
    objective_met: Optional[bool] = None
    progress_rating: Optional[str] = None
    prompt_level: Optional[str] = None
    time_spent_minutes: Optional[int] = None
    student_engagement: Optional[str] = None
    data_collection_method: Optional[str] = None


class SessionObjectiveResponse(SessionObjectiveBase):
    id: int
    therapy_session_id: int
    created_date: datetime
    modified_date: datetime
    
    # Include objective details
    objective_description: Optional[str] = None
    goal_description: Optional[str] = None
    success_rate: Optional[float] = None

    class Config:
        from_attributes = True


class TherapySessionBase(BaseModel):
    student_id: int = Field(..., description="Student receiving therapy")
    appointment_id: Optional[int] = Field(None, description="Linked appointment (null for unscheduled)")
    time_block_id: Optional[int] = Field(None, description="Linked time block for group sessions")
    session_date: datetime = Field(..., description="Date of the therapy session")
    start_time: Optional[datetime] = Field(None, description="Actual session start time")
    end_time: Optional[datetime] = Field(None, description="Actual session end time")
    planned_duration_minutes: Optional[int] = Field(None, description="Planned session duration")
    actual_duration_minutes: Optional[int] = Field(None, description="Actual session duration")
    session_type: str = Field("individual", description="individual, group, assessment, consultation")
    status: str = Field("planned", description="planned, in_progress, completed, cancelled, no_show")
    created_from: Optional[str] = Field(None, description="appointment, manual, emergency, walk_in")
    prep_notes: Optional[str] = Field(None, description="Pre-session preparation notes")
    session_notes: Optional[str] = Field(None, description="Notes taken during/after session")
    therapist_observations: Optional[str] = Field(None, description="Clinical observations")
    student_engagement: Optional[str] = Field(None, description="high, medium, low, variable")
    materials_used: Optional[str] = Field(None, description="Materials and resources used")
    goals_addressed: bool = Field(False, description="Whether planned goals were addressed")
    session_quality: Optional[str] = Field(None, description="excellent, good, fair, poor")
    follow_up_needed: bool = Field(False, description="Whether follow-up is needed")
    follow_up_notes: Optional[str] = Field(None, description="Follow-up recommendations")


class TherapySessionCreate(TherapySessionBase):
    # Include goals and objectives for session planning
    planned_goals: Optional[List[SessionGoalCreate]] = Field(default_factory=list, description="Goals planned for this session")
    planned_objectives: Optional[List[SessionObjectiveCreate]] = Field(default_factory=list, description="Objectives planned for this session")


class TherapySessionUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actual_duration_minutes: Optional[int] = None
    status: Optional[str] = None
    prep_notes: Optional[str] = None
    session_notes: Optional[str] = None
    therapist_observations: Optional[str] = None
    student_engagement: Optional[str] = None
    materials_used: Optional[str] = None
    goals_addressed: Optional[bool] = None
    session_quality: Optional[str] = None
    follow_up_needed: Optional[bool] = None
    follow_up_notes: Optional[str] = None


class TherapySessionResponse(TherapySessionBase):
    id: int
    created_date: datetime
    modified_date: datetime
    created_by: Optional[str] = None
    
    # Computed properties
    duration_minutes: int = 0
    is_scheduled: bool = False
    is_group_session: bool = False
    is_active: bool = False
    is_completed: bool = False
    
    # Related data counts
    planned_goals_count: int = 0
    worked_goals_count: int = 0
    planned_objectives_count: int = 0
    worked_objectives_count: int = 0
    progress_entries_count: int = 0
    
    # Related data (optional, for detailed responses)
    session_goals: Optional[List[SessionGoalResponse]] = None
    session_objectives: Optional[List[SessionObjectiveResponse]] = None
    
    # Student info (for convenience)
    student_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class TherapySessionSummary(BaseModel):
    """Lightweight summary for list views"""
    id: int
    student_id: int
    student_name: Optional[str] = None
    session_date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: int = 0
    session_type: str
    status: str
    is_scheduled: bool = False
    goals_addressed: bool = False
    session_quality: Optional[str] = None
    created_date: datetime

    class Config:
        from_attributes = True


class TherapySessionFilters(BaseModel):
    """Filters for therapy session queries"""
    student_id: Optional[int] = None
    appointment_id: Optional[int] = None
    time_block_id: Optional[int] = None
    session_type: Optional[str] = None
    status: Optional[str] = None
    created_from: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    session_quality: Optional[str] = None
    goals_addressed: Optional[bool] = None
    follow_up_needed: Optional[bool] = None
    include_goals: bool = False
    include_objectives: bool = False


class PlannedObjectiveForSession(BaseModel):
    """Objective to plan for a session with optional pre-session notes"""
    objective_id: int
    goal_id: int
    priority: Optional[int] = 1
    pre_session_notes: Optional[str] = None

class StartSessionRequest(BaseModel):
    """Request to start a therapy session"""
    student_id: int
    session_type: str = "unscheduled"  # unscheduled, link_existing, create_appointment
    appointment_id: Optional[int] = None  # For linking to existing appointment
    create_appointment: bool = False  # Whether to create appointment
    planned_duration_minutes: Optional[int] = 30  # Default duration
    prep_notes: Optional[str] = None
    planned_goals: Optional[List[int]] = Field(default_factory=list, description="Goal IDs to work on")
    planned_objectives: Optional[List[int]] = Field(default_factory=list, description="Objective IDs to work on")
    planned_objectives_with_notes: Optional[List[PlannedObjectiveForSession]] = Field(default_factory=list, description="Objectives with pre-session notes")


class CompleteSessionRequest(BaseModel):
    """Request to complete a therapy session"""
    session_notes: Optional[str] = None
    therapist_observations: Optional[str] = None
    student_engagement: Optional[str] = None
    materials_used: Optional[str] = None
    goals_addressed: bool = False
    session_quality: Optional[str] = None
    follow_up_needed: bool = False
    follow_up_notes: Optional[str] = None
    create_appointment_for_unscheduled: bool = False  # Offer to create appointment for unscheduled sessions
