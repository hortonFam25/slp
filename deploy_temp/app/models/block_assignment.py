from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class BlockAssignment(Base):
    __tablename__ = "block_assignments"

    id = Column(Integer, primary_key=True, index=True)
    time_block_id = Column(Integer, ForeignKey('time_blocks.id'), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    
    # Assignment details
    status = Column(String(20), nullable=False, server_default='assigned', index=True)
    assignment_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    removed_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    created_by = Column(String(100), nullable=True)

    # Relationships
    time_block = relationship("TimeBlock", back_populates="block_assignments")
    student = relationship("Student", back_populates="block_assignments")

    @property
    def is_active(self) -> bool:
        """Check if assignment is currently active"""
        return self.status == 'assigned'

    @property
    def duration_display(self) -> str:
        """Display duration from assignment to removal (if applicable)"""
        if self.removed_date and self.assignment_date:
            delta = self.removed_date - self.assignment_date
            days = delta.days
            if days == 0:
                return "Same day"
            elif days == 1:
                return "1 day"
            else:
                return f"{days} days"
        return "Active"
