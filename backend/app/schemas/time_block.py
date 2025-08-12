from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TimeBlockBase(BaseModel):
    teacher_id: Optional[int] = Field(None, description="Teacher conducting the block")
    school_id: Optional[int] = Field(None, description="School location")
    start_datetime: datetime = Field(..., description="Block start time")
    end_datetime: datetime = Field(..., description="Block end time")
    block_type: str = Field("group_therapy", description="Type of block (group_therapy, assessment_block)")
    title: str = Field(..., description="Block title/description")
    max_students: Optional[int] = Field(None, description="Maximum number of students")
    location: Optional[str] = Field(None, description="Specific location/room")
    notes: Optional[str] = Field(None, description="Additional notes")
    am_pm_indicator: Optional[str] = Field(None, description="AM/PM or custom indicator")
    status: str = Field("active", description="Block status (active, cancelled, completed)")


class TimeBlockCreate(TimeBlockBase):
    pass


class TimeBlockUpdate(BaseModel):
    teacher_id: Optional[int] = None
    school_id: Optional[int] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    block_type: Optional[str] = None
    title: Optional[str] = None
    max_students: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    am_pm_indicator: Optional[str] = None
    status: Optional[str] = None


class TimeBlockRead(TimeBlockBase):
    id: int
    created_date: datetime
    modified_date: datetime
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class TimeBlockSummary(BaseModel):
    id: int
    teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    block_type: str
    title: str
    max_students: Optional[int] = None
    location: Optional[str] = None
    status: str
    current_student_count: int
    available_spots: int
    duration_minutes: int

    class Config:
        from_attributes = True


class TimeBlockWithStudents(TimeBlockRead):
    teacher_name: Optional[str] = None
    school_name: Optional[str] = None
    duration_minutes: int
    current_student_count: int
    available_spots: int
    is_full: bool
    assigned_students: List["StudentSummary"] = []

    class Config:
        from_attributes = True


# Time Block Activity Schemas
class TimeBlockActivityBase(BaseModel):
    start_minute: int = Field(..., description="Start minute from block start (0, 5, 10, etc.)")
    duration_minutes: int = Field(5, description="Duration in minutes (default 5)")
    activity_name: str = Field(..., description="Name of the activity")
    activity_type: Optional[str] = Field(None, description="Type of activity (warm_up, main_activity, etc.)")
    description: Optional[str] = Field(None, description="Activity description")
    materials_needed: Optional[str] = Field(None, description="Materials needed for activity")
    notes: Optional[str] = Field(None, description="Additional notes")
    sequence_order: int = Field(..., description="Order of activity in sequence")


class TimeBlockActivityCreate(TimeBlockActivityBase):
    time_block_id: int = Field(..., description="ID of the time block")


class TimeBlockActivityUpdate(BaseModel):
    start_minute: Optional[int] = None
    duration_minutes: Optional[int] = None
    activity_name: Optional[str] = None
    activity_type: Optional[str] = None
    description: Optional[str] = None
    materials_needed: Optional[str] = None
    notes: Optional[str] = None
    sequence_order: Optional[int] = None


class TimeBlockActivityRead(TimeBlockActivityBase):
    id: int
    time_block_id: int
    created_date: datetime
    modified_date: datetime
    created_by: Optional[str] = None
    
    class Config:
        from_attributes = True


# Enhanced TimeBlock schema with activities
class TimeBlockWithActivities(TimeBlockWithStudents):
    activities: List[TimeBlockActivityRead] = []


# Time Block Scheduling Schemas
class TimeBlockScheduleRequest(BaseModel):
    time_block_id: int = Field(..., description="ID of time block to schedule")
    recurring_config: Optional[dict] = Field(None, description="Recurring schedule configuration")
    student_goal_assignments: Optional[dict] = Field(None, description="Goal/objective assignments per student")


class TimeBlockScheduleResponse(BaseModel):
    appointments_created: List[dict]
    conflicts: List[dict]
    total_appointments: int
    total_conflicts: int
    series_id: Optional[str] = None
    schedule_dates: List[str]


# Import here to avoid circular imports
from app.schemas.student import StudentSummary
TimeBlockWithStudents.model_rebuild()
