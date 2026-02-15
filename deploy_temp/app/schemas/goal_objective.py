from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class GoalObjectiveBase(BaseModel):
    objective_number: int = Field(..., ge=1, le=10, description="Objective sequence number (1-10)")
    objective_description: str = Field(..., min_length=1, description="Detailed objective description")
    progress_status: Optional[str] = Field(None, max_length=50, description="Current progress status")
    schedule_frequency: Optional[str] = Field(None, max_length=50, description="Tracking schedule (e.g., monthly, weekly)")


class GoalObjectiveCreate(GoalObjectiveBase):
    goal_id: int = Field(..., description="ID of the parent goal")


class GoalObjectiveUpdate(BaseModel):
    objective_description: Optional[str] = Field(None, min_length=1, description="Detailed objective description")
    progress_status: Optional[str] = Field(None, max_length=50, description="Current progress status")
    schedule_frequency: Optional[str] = Field(None, max_length=50, description="Tracking schedule")


class GoalObjectiveRead(GoalObjectiveBase):
    id: int
    goal_id: int
    created_date: datetime
    modified_date: datetime
    progress_count: int = Field(0, description="Number of progress entries")

    class Config:
        from_attributes = True


class ObjectiveProgressEntryBase(BaseModel):
    progress_date: date = Field(..., description="Date of progress entry")
    progress_on_objective: Optional[str] = Field(None, max_length=100, description="Progress measurement/status")
    progress_comments: Optional[str] = Field(None, description="Detailed progress notes")
    therapist_initials: Optional[str] = Field(None, max_length=10, description="Therapist/clinician initials")
    session_type: Optional[str] = Field(None, max_length=50, description="Type of session")


class ObjectiveProgressEntryCreate(ObjectiveProgressEntryBase):
    objective_id: int = Field(..., description="ID of the objective")


class ObjectiveProgressEntryUpdate(BaseModel):
    progress_date: Optional[date] = None
    progress_on_objective: Optional[str] = Field(None, max_length=100)
    progress_comments: Optional[str] = None
    therapist_initials: Optional[str] = Field(None, max_length=10)
    session_type: Optional[str] = Field(None, max_length=50)


class ObjectiveProgressEntryRead(ObjectiveProgressEntryBase):
    id: int
    objective_id: int
    student_id: Optional[int] = Field(None, description="Student ID (derived from objective)")
    goal_id: Optional[int] = Field(None, description="Goal ID (derived from objective)")
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True


# Enhanced schemas for complete goal structure
class GoalObjectiveWithProgress(GoalObjectiveRead):
    """Goal objective with its progress entries"""
    progress_entries: List[ObjectiveProgressEntryRead] = []
    latest_progress_entry: Optional[ObjectiveProgressEntryRead] = None

    class Config:
        from_attributes = True
