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
