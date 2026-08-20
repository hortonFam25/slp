from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class StudentTeacherAssignment(Base):
    __tablename__ = "student_teacher_assignments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False, index=True)
    subject = Column(String(100), nullable=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default='0')
    notes = Column(String(500), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint('student_id', 'teacher_id', 'subject', 'start_date', name='uq_student_teacher_assignment'),
    )

    # Relationships
    student = relationship("Student", back_populates="teacher_assignments")
    teacher = relationship("Teacher", back_populates="student_assignments")

    @property
    def is_current(self) -> bool:
        """Whether this assignment is currently active"""
        return self.end_date is None

    @property
    def duration_description(self) -> str:
        """Human-readable duration description"""
        if self.end_date is None:
            return f"Since {self.start_date.strftime('%m/%d/%Y')}"
        else:
            return f"{self.start_date.strftime('%m/%d/%Y')} - {self.end_date.strftime('%m/%d/%Y')}"

    @property
    def subject_display(self) -> str:
        """Subject display with fallback"""
        return self.subject or "General Education"
