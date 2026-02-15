from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AppointmentBase(BaseModel):
    student_id: int = Field(..., description="Student being scheduled")
    teacher_id: Optional[int] = Field(None, description="Teacher conducting the appointment")
    school_id: Optional[int] = Field(None, description="School location")
    time_block_id: Optional[int] = Field(None, description="Time block this appointment belongs to")
    start_datetime: datetime = Field(..., description="Appointment start time")
    end_datetime: datetime = Field(..., description="Appointment end time")
    appointment_type: str = Field("individual", description="Type of appointment (individual, group, assessment)")
    status: str = Field("scheduled", description="Appointment status (scheduled, completed, cancelled, no_show)")
    location: Optional[str] = Field(None, description="Specific location/room")
    notes: Optional[str] = Field(None, description="Additional notes")
    therapy_session_completed: bool = Field(False, description="Whether therapy session was completed")
    session_notes: Optional[str] = Field(None, description="Notes from completed session")


# Goal and objective planning schemas for appointment creation
class PlannedGoal(BaseModel):
    goal_id: int
    planned: bool = True
    worked_on: bool = False
    priority: int = 1

class PlannedObjective(BaseModel):
    objective_id: int
    goal_id: int
    planned: bool = True
    worked_on: bool = False
    priority: int = 1
    pre_session_notes: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    # Optional goal and objective planning for therapy sessions
    planned_goals: Optional[List[PlannedGoal]] = Field(None, description="Goals planned for this appointment")
    planned_objectives: Optional[List[PlannedObjective]] = Field(None, description="Objectives planned for this appointment")


class RecurringConfig(BaseModel):
    frequency: str = Field(..., description="Recurring frequency: 'weekly' or 'monthly'")
    interval: int = Field(..., description="Interval between occurrences (every X weeks/months)")
    days_of_week: List[int] = Field(..., description="Days of week (0=Sunday, 1=Monday, etc.)")
    end_type: str = Field(..., description="End condition: 'date' or 'occurrences'")
    end_date: Optional[datetime] = Field(None, description="End date for recurring series")
    max_occurrences: Optional[int] = Field(None, description="Maximum number of occurrences")


class RecurringAppointmentCreate(AppointmentBase):
    # Same appointment data as single appointment
    planned_goals: Optional[List[PlannedGoal]] = Field(None, description="Goals planned for each appointment")
    planned_objectives: Optional[List[PlannedObjective]] = Field(None, description="Objectives planned for each appointment")
    
    # Recurring configuration
    recurring_config: RecurringConfig = Field(..., description="Recurring appointment configuration")


class AppointmentUpdate(BaseModel):
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    school_id: Optional[int] = None
    time_block_id: Optional[int] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    appointment_type: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    therapy_session_completed: Optional[bool] = None
    session_notes: Optional[str] = None
    
    # Optional goal and objective planning for therapy sessions
    planned_goals: Optional[List[PlannedGoal]] = Field(None, description="Goals planned for this appointment")
    planned_objectives: Optional[List[PlannedObjective]] = Field(None, description="Objectives planned for this appointment")


class AppointmentRead(AppointmentBase):
    id: int
    created_date: datetime
    modified_date: datetime
    created_by: Optional[str] = None
    series_id: Optional[str] = Field(None, description="Series ID for recurring appointments")
    series_metadata: Optional[str] = Field(None, description="JSON metadata for the appointment series")

    class Config:
        from_attributes = True


class RecurringAppointmentResponse(BaseModel):
    appointments: List[AppointmentRead]
    total_created: int
    conflicts: Optional[List[str]] = Field(None, description="List of conflicting appointment times that were skipped")
    series_id: Optional[str] = Field(None, description="Series ID for the created recurring appointments")


class SeriesPatternUpdate(BaseModel):
    update_type: str = Field(..., description="Type of update: time_only, offset_only, or day_alignment")
    start_datetime: Optional[datetime] = Field(None, description="New start time")
    end_datetime: Optional[datetime] = Field(None, description="New end time")
    date_offset_days: Optional[int] = Field(None, description="Number of days to offset all appointments")
    target_day_of_week: Optional[int] = Field(None, description="Target day of week (0=Sunday, 6=Saturday)")
    notes: Optional[str] = Field(None, description="Updated notes")
    planned_goals: Optional[List[PlannedGoal]] = Field(None, description="Updated planned goals")
    planned_objectives: Optional[List[PlannedObjective]] = Field(None, description="Updated planned objectives")


class AppointmentSummary(BaseModel):
    id: int
    student_id: int
    student_name: str
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    time_block_id: Optional[int] = None
    start_datetime: datetime
    end_datetime: datetime
    appointment_type: str
    series_id: Optional[str] = Field(None, description="Series ID for recurring appointments")
    status: str
    location: Optional[str] = None
    notes: Optional[str] = None
    duration_minutes: int
    therapy_session_status: Optional[str] = Field(None, description="Status of linked therapy session")

    class Config:
        from_attributes = True


class AppointmentWithDetails(AppointmentRead):
    student_name: str
    teacher_name: Optional[str] = None
    school_name: Optional[str] = None
    duration_minutes: int
    can_start_session: bool

    class Config:
        from_attributes = True
