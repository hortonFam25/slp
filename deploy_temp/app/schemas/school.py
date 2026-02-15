from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class SchoolBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="School name")
    address: Optional[str] = Field(None, max_length=500, description="School address")
    phone: Optional[str] = Field(None, max_length=20, description="School phone number")
    email: Optional[str] = Field(None, max_length=100, description="School email address")
    district: Optional[str] = Field(None, max_length=100, description="School district")
    principal_name: Optional[str] = Field(None, max_length=100, description="Principal name")
    contact_person: Optional[str] = Field(None, max_length=100, description="Primary contact person")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact person phone")
    notes: Optional[str] = Field(None, description="Additional notes about the school")
    is_active: bool = Field(True, description="Whether school is active")


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    principal_name: Optional[str] = Field(None, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SchoolRead(SchoolBase):
    id: int
    created_date: datetime
    modified_date: datetime
    active_students_count: Optional[int] = Field(None, description="Number of active students")
    active_teachers_count: Optional[int] = Field(None, description="Number of active teachers")

    class Config:
        from_attributes = True


class SchoolSummary(BaseModel):
    """Lightweight school summary for dropdowns and lists"""
    id: int
    name: str
    district: Optional[str] = None
    is_active: bool
    active_students_count: Optional[int] = 0
    active_teachers_count: Optional[int] = 0

    class Config:
        from_attributes = True


# For teacher and student assignment schemas
class SchoolTeacherAssignmentBase(BaseModel):
    teacher_id: int
    school_id: int
    start_date: date = Field(..., description="Assignment start date")
    end_date: Optional[date] = Field(None, description="Assignment end date (null if current)")
    is_primary: bool = Field(False, description="Is this the teacher's primary school")
    notes: Optional[str] = Field(None, max_length=500, description="Assignment notes")


class SchoolTeacherAssignmentCreate(SchoolTeacherAssignmentBase):
    pass


class SchoolTeacherAssignmentUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)


class SchoolTeacherAssignmentRead(SchoolTeacherAssignmentBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_current: bool = Field(..., description="Whether this assignment is currently active")
    duration_description: str = Field(..., description="Human-readable duration")

    class Config:
        from_attributes = True
