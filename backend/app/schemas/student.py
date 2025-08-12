from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime

if TYPE_CHECKING:
    from app.schemas.eligibility import StudentEligibilityRead


class StudentBase(BaseModel):
    first: str = Field(..., min_length=1, max_length=100)
    last: str = Field(..., min_length=1, max_length=100)
    uic: Optional[str] = Field(None, max_length=50, description="Unique Identifier Code from legacy IEP system")
    grade_level: Optional[str] = Field(None, max_length=10)
    teacher_name: Optional[str] = Field(None, max_length=100)
    case_manager: Optional[str] = Field(None, max_length=100)
    enrollment_status: str = Field("Active", max_length=20)
    is_archived: bool = Field(False, description="Whether the student is archived")
    date_of_birth: Optional[date] = None
    
    # School assignment
    school_id: Optional[int] = Field(None, description="Assigned school ID")
    
    # IEP Date Fields
    iep_date: Optional[date] = Field(None, description="Current IEP date")
    annual_review_due_date: Optional[date] = Field(None, description="Annual IEP review due date")
    reevaluation_due_date: Optional[date] = Field(None, description="Re-evaluation due date (every 3 years)")
    iep_meeting_date: Optional[date] = Field(None, description="Last IEP meeting date")
    initial_evaluation_date: Optional[date] = Field(None, description="Initial evaluation date")
    eligibility_determination_date: Optional[date] = Field(None, description="Date eligibility was determined")


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    first: Optional[str] = Field(None, min_length=1, max_length=100)
    last: Optional[str] = Field(None, min_length=1, max_length=100)
    uic: Optional[str] = Field(None, max_length=50)
    grade_level: Optional[str] = Field(None, max_length=10)
    teacher_name: Optional[str] = Field(None, max_length=100)
    case_manager: Optional[str] = Field(None, max_length=100)
    enrollment_status: Optional[str] = Field(None, max_length=20)
    is_archived: Optional[bool] = None
    date_of_birth: Optional[date] = None
    
    # School assignment
    school_id: Optional[int] = None
    
    # IEP Date Fields
    iep_date: Optional[date] = None
    annual_review_due_date: Optional[date] = None
    reevaluation_due_date: Optional[date] = None
    iep_meeting_date: Optional[date] = None
    initial_evaluation_date: Optional[date] = None
    eligibility_determination_date: Optional[date] = None


class StudentRead(StudentBase):
    id: int
    created_date: datetime
    modified_date: datetime
    eligibilities: List['StudentEligibilityRead'] = []

    class Config:
        from_attributes = True


class StudentSummary(BaseModel):
    """Lightweight student model for lists and summaries"""
    id: int
    first: str
    last: str
    grade_level: Optional[str] = None
    case_manager: Optional[str] = None
    enrollment_status: str
    school_id: Optional[int] = None  # Added for scheduling functionality
    uic: Optional[str] = None  # Added for student identification

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    class Config:
        from_attributes = True


# Update forward references after all models are defined
from app.schemas.eligibility import StudentEligibilityRead
StudentRead.model_rebuild()
