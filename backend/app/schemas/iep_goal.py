from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from app.schemas.goal_objective import GoalObjectiveRead, GoalObjectiveWithProgress


class IEPGoalBase(BaseModel):
    goal_category_id: int = Field(..., description="ID of the goal category")
    goal_number: Optional[str] = Field(None, max_length=20, description="Goal number/identifier")
    goal_description: str = Field(..., min_length=1, description="Goal description")
    target_behavior: Optional[str] = Field(None, description="Target behavior/skill")
    baseline_data: Optional[str] = Field(None, max_length=500, description="Baseline data")
    target_criteria: str = Field(..., max_length=500, description="Target criteria for mastery")
    goal_status: str = Field("Active", max_length=20, description="Goal status")
    start_date: date = Field(..., description="Goal start date")
    end_date: Optional[date] = Field(None, description="Goal end date")
    mastery_date: Optional[date] = Field(None, description="Date goal was mastered")


class IEPGoalCreate(IEPGoalBase):
    student_id: int = Field(..., description="ID of the student")


class IEPGoalUpdate(BaseModel):
    goal_category_id: Optional[int] = None
    goal_number: Optional[str] = Field(None, max_length=20)
    goal_description: Optional[str] = Field(None, min_length=1)
    target_behavior: Optional[str] = None
    baseline_data: Optional[str] = Field(None, max_length=500)
    target_criteria: Optional[str] = Field(None, max_length=500)
    goal_status: Optional[str] = Field(None, max_length=20)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    mastery_date: Optional[date] = None


class IEPGoalRead(IEPGoalBase):
    id: int
    student_id: int
    created_date: datetime
    modified_date: datetime

    class Config:
        from_attributes = True


class IEPGoalWithObjectives(IEPGoalRead):
    """IEP Goal with its objectives and progress"""
    objectives: List[GoalObjectiveWithProgress] = []
    goal_category_name: Optional[str] = Field(None, description="Name of the goal category")

    class Config:
        from_attributes = True


class IEPGoalSummary(BaseModel):
    """Lightweight goal summary for lists"""
    id: int
    goal_number: Optional[str]
    goal_description: str
    goal_status: str
    start_date: date
    end_date: Optional[date]
    mastery_date: Optional[date]
    goal_category_name: Optional[str]
    objectives_count: int = Field(0, description="Number of objectives")

    class Config:
        from_attributes = True


# Schema for importing goals from CSV (matching your data structure)
class GoalCSVRow(BaseModel):
    """Schema for importing goal data from CSV"""
    goal: str = Field(..., description="Goal description")
    goal_type: str = Field(..., description="Goal type/category")
    goal_number: Optional[str] = Field(None, description="Goal number")
    
    # Objectives (up to 4)
    objective1: Optional[str] = None
    progress1: Optional[str] = None
    schedule1: Optional[str] = None
    prog_date1: Optional[str] = None
    prog_obj1: Optional[str] = None
    prog_comments1: Optional[str] = None
    prog_initials1: Optional[str] = None
    
    objective2: Optional[str] = None
    progress2: Optional[str] = None
    schedule2: Optional[str] = None
    prog_date2: Optional[str] = None
    prog_obj2: Optional[str] = None
    prog_comments2: Optional[str] = None
    prog_initials2: Optional[str] = None
    
    objective3: Optional[str] = None
    progress3: Optional[str] = None
    schedule3: Optional[str] = None
    prog_date3: Optional[str] = None
    prog_obj3: Optional[str] = None
    prog_comments3: Optional[str] = None
    prog_initials3: Optional[str] = None
    
    objective4: Optional[str] = None
    progress4: Optional[str] = None
    schedule4: Optional[str] = None
    prog_date4: Optional[str] = None
    prog_obj4: Optional[str] = None
    prog_comments4: Optional[str] = None
    prog_initials4: Optional[str] = None
