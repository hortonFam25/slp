from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class TimeBlock(Base):
    __tablename__ = "time_blocks"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=True, index=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True, index=True)
    
    # Time scheduling
    start_datetime = Column(DateTime, nullable=False, index=True)
    end_datetime = Column(DateTime, nullable=False, index=True)
    
    # Block details
    block_type = Column(String(50), nullable=False, server_default='group_therapy', index=True)
    title = Column(String(200), nullable=False)
    max_students = Column(Integer, nullable=True)
    location = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    am_pm_indicator = Column(String(10), nullable=True, index=True)  # 'AM', 'PM', or custom
    
    # Status
    status = Column(String(20), nullable=False, server_default='active', index=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    created_by = Column(String(100), nullable=True)

    # Relationships
    teacher = relationship("Teacher", back_populates="time_blocks")
    school = relationship("School", back_populates="time_blocks")
    block_assignments = relationship("BlockAssignment", back_populates="time_block", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="time_block", cascade="all, delete-orphan")
    therapy_sessions = relationship("TherapySession", back_populates="time_block", cascade="all, delete-orphan")
    activities = relationship("TimeBlockActivity", back_populates="time_block", cascade="all, delete-orphan", order_by="TimeBlockActivity.sequence_order")

    @property
    def duration_minutes(self) -> int:
        """Calculate block duration in minutes"""
        if self.start_datetime and self.end_datetime:
            delta = self.end_datetime - self.start_datetime
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def current_student_count(self) -> int:
        """Count of currently assigned students"""
        return len([assignment for assignment in self.block_assignments if assignment.status == 'assigned'])

    @property
    def is_full(self) -> bool:
        """Check if block is at capacity"""
        if not self.max_students:
            return False
        return self.current_student_count >= self.max_students

    @property
    def available_spots(self) -> int:
        """Number of available spots remaining"""
        if not self.max_students:
            return 999  # Unlimited
        return max(0, self.max_students - self.current_student_count)

    @property
    def assigned_students(self):
        """List of students currently assigned to this block"""
        return [assignment.student for assignment in self.block_assignments 
                if assignment.status == 'assigned']
