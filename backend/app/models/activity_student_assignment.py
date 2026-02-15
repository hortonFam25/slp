from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class ActivityStudentAssignment(Base):
    __tablename__ = "activity_student_assignments"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey('time_block_activities.id'), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    
    # Assignment details
    status = Column(String(20), nullable=False, server_default='assigned', index=True)  # 'assigned', 'completed', 'skipped'
    notes = Column(String(500), nullable=True)  # Optional notes about this student's participation
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    created_by = Column(String(100), nullable=True)

    # Relationships
    activity = relationship("TimeBlockActivity", back_populates="student_assignments")
    student = relationship("Student", back_populates="activity_assignments")

    def __repr__(self):
        return f"<ActivityStudentAssignment(id={self.id}, activity_id={self.activity_id}, student_id={self.student_id}, status='{self.status}')>"
