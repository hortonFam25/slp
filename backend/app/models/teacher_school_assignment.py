from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class TeacherSchoolAssignment(Base):
    __tablename__ = "teacher_school_assignments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default='0')
    notes = Column(String(500), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint('teacher_id', 'school_id', 'start_date', name='uq_teacher_school_assignment'),
    )

    # Relationships
    teacher = relationship("Teacher", back_populates="school_assignments")
    school = relationship("School", back_populates="teacher_assignments")

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
