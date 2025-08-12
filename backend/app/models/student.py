from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    first = Column(String(100), nullable=False)
    last = Column(String(100), nullable=False)
    uic = Column(String(50), unique=True, nullable=True, index=True)
    grade_level = Column(String(10), nullable=True, index=True)
    teacher_name = Column(String(100), nullable=True)
    case_manager = Column(String(100), nullable=True, index=True)
    enrollment_status = Column(String(20), nullable=False, server_default='Active', index=True)
    is_archived = Column(Boolean, nullable=False, server_default='0', index=True)
    date_of_birth = Column(Date, nullable=True)
    
    # IEP Date Fields
    iep_date = Column(Date, nullable=True, index=True)
    annual_review_due_date = Column(Date, nullable=True, index=True)
    reevaluation_due_date = Column(Date, nullable=True, index=True)
    iep_meeting_date = Column(Date, nullable=True)
    initial_evaluation_date = Column(Date, nullable=True)
    eligibility_determination_date = Column(Date, nullable=True)
    
    # School assignment
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True, index=True)
    
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    service_information = relationship("ServiceInformation", back_populates="student")
    iep_goals = relationship("IEPGoal", back_populates="student")
    progress_tracking = relationship("ProgressTracking", back_populates="student")
    assessment_data = relationship("AssessmentData", back_populates="student")
    eligibilities = relationship("StudentEligibility", back_populates="student")
    school = relationship("School", back_populates="students")
    teacher_assignments = relationship("StudentTeacherAssignment", back_populates="student")
    appointments = relationship("Appointment", back_populates="student")
    block_assignments = relationship("BlockAssignment", back_populates="student")
    therapy_sessions = relationship("TherapySession", back_populates="student")

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"
    
    @property
    def is_active(self) -> bool:
        """Check if student is active (not archived)"""
        return not self.is_archived
    
    @property
    def is_annual_review_due(self) -> bool:
        """Check if annual review is due or overdue"""
        if not self.annual_review_due_date:
            return False
        from datetime import date
        return date.today() >= self.annual_review_due_date
    
    @property
    def is_reevaluation_due(self) -> bool:
        """Check if re-evaluation is due or overdue"""
        if not self.reevaluation_due_date:
            return False
        from datetime import date
        return date.today() >= self.reevaluation_due_date
    
    @property
    def days_until_annual_review(self) -> int | None:
        """Days until annual review due date (negative if overdue)"""
        if not self.annual_review_due_date:
            return None
        from datetime import date
        return (self.annual_review_due_date - date.today()).days
    
    @property
    def days_until_reevaluation(self) -> int | None:
        """Days until re-evaluation due date (negative if overdue)"""
        if not self.reevaluation_due_date:
            return None
        from datetime import date
        return (self.reevaluation_due_date - date.today()).days
    
    @property
    def current_teachers(self) -> list:
        """List of teachers currently assigned to this student"""
        return [assignment.teacher for assignment in self.teacher_assignments 
                if assignment.end_date is None and assignment.teacher.is_active]
    
    @property
    def primary_teacher(self):
        """Primary teacher assignment if any"""
        primary_assignments = [assignment for assignment in self.teacher_assignments 
                             if assignment.is_primary and assignment.end_date is None]
        return primary_assignments[0].teacher if primary_assignments else None
    
    @property
    def school_name(self) -> str:
        """School name or 'Not Assigned'"""
        return self.school.name if self.school else "Not Assigned"


