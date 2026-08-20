from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True, index=True)
    principal_name = Column(String(100), nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1')
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    students = relationship("Student", back_populates="school")
    teacher_assignments = relationship("TeacherSchoolAssignment", back_populates="school")
    appointments = relationship("Appointment", back_populates="school")
    time_blocks = relationship("TimeBlock", back_populates="school")

    @property
    def full_name(self) -> str:
        """Full school name with district if available"""
        if self.district:
            return f"{self.name} ({self.district})"
        return self.name

    @property
    def active_teachers_count(self) -> int:
        """Count of currently active teachers at this school"""
        return len([assignment for assignment in self.teacher_assignments 
                   if assignment.end_date is None and assignment.teacher.is_active])

    @property
    def active_students_count(self) -> int:
        """Count of currently active students at this school"""
        return len([student for student in self.students 
                   if student.enrollment_status == 'Active'])
