from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TeacherAssignmentForScheduling(BaseModel):
    """Teacher assignment info for scheduling views"""
    teacher_id: int
    teacher_name: str = Field(..., description="Full name of the teacher")
    subject: Optional[str] = Field(None, description="Subject or class")
    is_primary: bool = Field(False, description="Is this the student's primary teacher")
    
    class Config:
        from_attributes = True


class SchoolForScheduling(BaseModel):
    """School info for scheduling views"""
    id: int
    name: str
    district_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class AppointmentSummaryForStudent(BaseModel):
    """Summary of student's appointments for scheduling views"""
    id: int
    start_datetime: datetime
    end_datetime: datetime
    appointment_type: str
    status: str
    teacher_name: Optional[str] = None
    location: Optional[str] = None
    
    class Config:
        from_attributes = True


class StudentScheduleView(BaseModel):
    """Comprehensive student data for scheduling functionality"""
    # Basic student info
    id: int
    student_alias: str
    first: str
    last: str
    uic: Optional[str] = None
    grade_level: Optional[str] = None
    case_manager_name: Optional[str] = None  # Computed from relationship
    enrollment_status: str
    
    # School relationship
    school_id: Optional[int] = None
    school: Optional[SchoolForScheduling] = None
    
    # Teacher relationships
    teacher_assignments: List[TeacherAssignmentForScheduling] = []
    primary_teacher: Optional[TeacherAssignmentForScheduling] = None
    
    # Scheduling summary (for current week/date range)
    current_appointments: List[AppointmentSummaryForStudent] = []
    appointment_count: int = 0
    has_appointments: bool = False
    
    @property
    def full_name(self) -> str:
        first_clean = (self.first or "").strip().replace('\r\n', '')
        last_clean = (self.last or "").strip().replace('\r\n', '')
        return f"{first_clean} {last_clean}".strip()
    
    @property
    def school_name(self) -> str:
        return self.school.name if self.school else "No School Assigned"
    
    @property
    def primary_teacher_name(self) -> str:
        if self.primary_teacher:
            return self.primary_teacher.teacher_name
        elif self.case_manager_name:
            return self.case_manager_name.strip().replace('\r\n', '')
        else:
            return "No Teacher Assigned"
    
    class Config:
        from_attributes = True


class StudentScheduleFilters(BaseModel):
    """Filters for student scheduling views"""
    school_id: Optional[int] = None
    teacher_id: Optional[int] = None
    grade_level: Optional[str] = None
    enrollment_status: Optional[str] = None
    start_date: Optional[str] = None  # For filtering by appointment date range
    end_date: Optional[str] = None
    has_appointments: Optional[bool] = None  # True=scheduled, False=unscheduled, None=all
