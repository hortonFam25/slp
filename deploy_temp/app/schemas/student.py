from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime

if TYPE_CHECKING:
    from app.schemas.eligibility import StudentEligibilityRead

class SchoolForStudent(BaseModel):
    """School info for student relationships"""
    id: int
    name: str
    district: Optional[str] = None

    class Config:
        from_attributes = True


class StudentBase(BaseModel):
    first: str = Field(..., min_length=1, max_length=100)
    last: str = Field(..., min_length=1, max_length=100)
    uic: Optional[str] = Field(None, max_length=50, description="Unique Identifier Code from legacy IEP system")
    grade_level: Optional[str] = Field(None, max_length=35)
    enrollment_status: str = Field("Active", max_length=20)
    is_archived: bool = Field(False, description="Whether the student is archived")
    date_of_birth: Optional[date] = None
    
    # School assignment
    school_id: Optional[int] = Field(None, description="Assigned school ID")
    
    # Teacher and case manager relationships
    teacher_id: Optional[int] = Field(None, description="Assigned teacher ID")
    case_manager_id: Optional[int] = Field(None, description="Assigned case manager ID")
    
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
    grade_level: Optional[str] = Field(None, max_length=35)
    enrollment_status: Optional[str] = Field(None, max_length=20)
    is_archived: Optional[bool] = None
    date_of_birth: Optional[date] = None
    
    # School assignment
    school_id: Optional[int] = None
    
    # Teacher and case manager relationships (primary fields)
    teacher_id: Optional[int] = Field(None, description="Assigned teacher ID")
    case_manager_id: Optional[int] = Field(None, description="Assigned case manager ID")
    
    # IEP Date Fields
    iep_date: Optional[date] = None
    annual_review_due_date: Optional[date] = None
    reevaluation_due_date: Optional[date] = None
    iep_meeting_date: Optional[date] = None
    initial_evaluation_date: Optional[date] = None
    eligibility_determination_date: Optional[date] = None


class TeacherSummary(BaseModel):
    """Lightweight teacher info for student relationships"""
    id: int
    first_name: str
    last_name: str
    title: Optional[str] = None
    email: Optional[str] = None
    full_name: str
    display_name: str

    class Config:
        from_attributes = True


class StudentRead(BaseModel):
    """Student read model with new relationship structure"""
    id: int
    first: str
    last: str
    uic: Optional[str] = None
    grade_level: Optional[str] = None
    enrollment_status: str
    is_archived: bool
    date_of_birth: Optional[date] = None
    school_id: Optional[int] = None
    created_date: datetime
    modified_date: datetime
    
    # New relationship fields (primary)
    teacher_id: Optional[int] = None
    case_manager_id: Optional[int] = None
    teacher: Optional[TeacherSummary] = None
    case_manager: Optional[TeacherSummary] = None
    school: Optional[SchoolForStudent] = None  # School relationship data
    
    # IEP Date Fields
    iep_date: Optional[date] = None
    annual_review_due_date: Optional[date] = None
    reevaluation_due_date: Optional[date] = None
    iep_meeting_date: Optional[date] = None
    initial_evaluation_date: Optional[date] = None
    eligibility_determination_date: Optional[date] = None
    
    eligibilities: List['StudentEligibilityRead'] = []


    class Config:
        from_attributes = True


class StudentSummary(BaseModel):
    """Lightweight student model for lists and summaries"""
    id: int
    first: str
    last: str
    grade_level: Optional[str] = None
    enrollment_status: str
    school_id: Optional[int] = None  # Added for scheduling functionality
    uic: Optional[str] = None  # Added for student identification
    
    # New relationship fields (primary)
    teacher_id: Optional[int] = None
    case_manager_id: Optional[int] = None
    teacher: Optional[TeacherSummary] = None
    case_manager: Optional[TeacherSummary] = None

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"
    
    @property
    def teacher_name(self) -> Optional[str]:
        """Get teacher name from relationship"""
        if self.teacher:
            return self.teacher.display_name
        return None
    
    @property
    def case_manager_name(self) -> Optional[str]:
        """Get case manager name from relationship"""
        if self.case_manager:
            return self.case_manager.display_name
        return None

    class Config:
        from_attributes = True


# Update forward references after all models are defined
from app.schemas.eligibility import StudentEligibilityRead
StudentRead.model_rebuild()
