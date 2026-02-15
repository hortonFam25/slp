from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class TimeBlockActivity(Base):
    __tablename__ = "time_block_activities"

    id = Column(Integer, primary_key=True, index=True)
    time_block_id = Column(Integer, ForeignKey('time_blocks.id'), nullable=False, index=True)
    
    # Activity timing (in 5-minute increments)
    start_minute = Column(Integer, nullable=False)  # Minutes from start of block (0, 5, 10, etc.)
    duration_minutes = Column(Integer, nullable=False, server_default='5')  # Default 5 minutes
    
    # Absolute timing (new fields for enhanced functionality)
    start_datetime = Column(DateTime, nullable=True, index=True)  # Actual start time
    end_datetime = Column(DateTime, nullable=True, index=True)    # Actual end time
    
    # Activity details
    activity_name = Column(String(200), nullable=False)
    activity_type = Column(String(50), nullable=True)  # 'warm_up', 'main_activity', 'transition', 'closing', etc.
    description = Column(Text, nullable=True)
    materials_needed = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Ordering
    sequence_order = Column(Integer, nullable=False, index=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    created_by = Column(String(100), nullable=True)

    # Relationships
    time_block = relationship("TimeBlock", back_populates="activities")
    student_assignments = relationship("ActivityStudentAssignment", back_populates="activity", cascade="all, delete-orphan")

    @property
    def end_minute(self) -> int:
        """Calculate end minute from start of block"""
        return self.start_minute + self.duration_minutes

    @property
    def time_range_display(self) -> str:
        """Display time range within the block"""
        return f"{self.start_minute}m - {self.end_minute}m"
    
    @property
    def actual_start_time(self):
        """Calculate actual start time based on time block start"""
        if self.time_block and self.time_block.start_datetime:
            from datetime import timedelta
            return self.time_block.start_datetime + timedelta(minutes=self.start_minute)
        return None
    
    @property
    def actual_end_time(self):
        """Calculate actual end time based on time block start"""
        if self.time_block and self.time_block.start_datetime:
            from datetime import timedelta
            return self.time_block.start_datetime + timedelta(minutes=self.end_minute)
        return None

    @property
    def assigned_students(self):
        """List of students assigned to this activity"""
        return [assignment.student for assignment in self.student_assignments 
                if assignment.status == 'assigned']

    def validate_time_within_block(self) -> dict:
        """Validate that activity times are within the time block timeframe"""
        if not self.time_block:
            return {"valid": False, "error": "No time block associated"}
        
        block_start = self.time_block.start_datetime
        block_end = self.time_block.end_datetime
        
        if not block_start or not block_end:
            return {"valid": False, "error": "Time block has no start/end time"}
        
        # Check if using datetime fields
        if self.start_datetime and self.end_datetime:
            if self.start_datetime < block_start:
                return {"valid": False, "error": f"Activity starts before time block ({self.start_datetime} < {block_start})"}
            if self.end_datetime > block_end:
                return {"valid": False, "error": f"Activity ends after time block ({self.end_datetime} > {block_end})"}
            if self.start_datetime >= self.end_datetime:
                return {"valid": False, "error": "Activity start time must be before end time"}
        else:
            # Check using minute-based fields
            if self.start_minute < 0:
                return {"valid": False, "error": "Activity cannot start before time block"}
            if self.end_minute > self.time_block.duration_minutes:
                return {"valid": False, "error": f"Activity ends after time block ({self.end_minute}m > {self.time_block.duration_minutes}m)"}
        
        return {"valid": True}

    def sync_datetime_with_minutes(self):
        """Sync start_datetime/end_datetime with start_minute/duration_minutes"""
        if self.time_block and self.time_block.start_datetime:
            from datetime import timedelta
            self.start_datetime = self.time_block.start_datetime + timedelta(minutes=self.start_minute)
            self.end_datetime = self.time_block.start_datetime + timedelta(minutes=self.start_minute + self.duration_minutes)

    def sync_minutes_with_datetime(self):
        """Sync start_minute/duration_minutes with start_datetime/end_datetime"""
        if self.time_block and self.time_block.start_datetime and self.start_datetime and self.end_datetime:
            start_delta = self.start_datetime - self.time_block.start_datetime
            end_delta = self.end_datetime - self.time_block.start_datetime
            
            self.start_minute = int(start_delta.total_seconds() / 60)
            self.duration_minutes = int((self.end_datetime - self.start_datetime).total_seconds() / 60)
