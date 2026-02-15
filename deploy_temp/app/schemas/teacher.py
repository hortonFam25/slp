from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class TeacherBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, description="Teacher first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Teacher last name")
    email: Optional[str] = Field(None, max_length=100, description="Teacher email")
    phone: Optional[str] = Field(None, max_length=20, description="Teacher phone number")
    title: Optional[str] = Field(None, max_length=100, description="Teacher title/position")
    department: Optional[str] = Field(None, max_length=100, description="Department or subject area")
    room_number: Optional[str] = Field(None, max_length=20, description="Classroom or office room number")
    preferred_contact_method: Optional[str] = Field(None, max_length=20, description="Preferred contact method")
    notes: Optional[str] = Field(None, description="Additional notes about the teacher")
    is_active: bool = Field(True, description="Whether teacher is active")


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    room_number: Optional[str] = Field(None, max_length=20)
    preferred_contact_method: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherRead(TeacherBase):
    id: int
    created_date: datetime
    modified_date: datetime
    full_name: str = Field(..., description="Full teacher name")
    display_name: str = Field(..., description="Display name with title")
    current_students_count: Optional[int] = Field(None, description="Number of current students")
    primary_school_name: Optional[str] = Field(None, description="Primary school name")
    current_schools_names: Optional[List[str]] = Field(None, description="List of current school names")
    active_schools_count: Optional[int] = Field(None, description="Number of active school assignments")

    class Config:
        from_attributes = True


class TeacherSummary(BaseModel):
    """Lightweight teacher summary for dropdowns and lists"""
    id: int
    first_name: str
    last_name: str
    full_name: str
    title: Optional[str] = None
    display_name: str
    email: Optional[str] = None
    is_active: bool
    current_students_count: Optional[int] = 0

    class Config:
        from_attributes = True


# For student-teacher assignment schemas
class StudentTeacherAssignmentBase(BaseModel):
    student_id: int
    teacher_id: int
    subject: Optional[str] = Field(None, max_length=100, description="Subject or class")
    start_date: date = Field(..., description="Assignment start date")
    end_date: Optional[date] = Field(None, description="Assignment end date (null if current)")
    is_primary: bool = Field(False, description="Is this the student's primary teacher")
    notes: Optional[str] = Field(None, max_length=500, description="Assignment notes")


class StudentTeacherAssignmentCreate(StudentTeacherAssignmentBase):
    pass


class StudentTeacherAssignmentUpdate(BaseModel):
    subject: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)


class StudentTeacherAssignmentRead(StudentTeacherAssignmentBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_current: bool = Field(..., description="Whether this assignment is currently active")
    duration_description: str = Field(..., description="Human-readable duration")
    subject_display: str = Field(..., description="Subject with fallback")

    class Config:
        from_attributes = True
