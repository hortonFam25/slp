from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship
import json
from app.db.base import Base


class TherapySession(Base):
    __tablename__ = "therapy_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey('appointments.id'), nullable=True, index=True)
    time_block_id = Column(Integer, ForeignKey('time_blocks.id'), nullable=True, index=True)
    
    # Session timing
    session_date = Column(DateTime, nullable=False, index=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    planned_duration_minutes = Column(Integer, nullable=True)
    actual_duration_minutes = Column(Integer, nullable=True)
    
    # Session details
    session_type = Column(String(50), nullable=False, server_default='individual', index=True)
    status = Column(String(20), nullable=False, server_default='planned', index=True)
    created_from = Column(String(50), nullable=True)
    
    # Session content
    prep_notes = Column(Text, nullable=True)
    session_notes = Column(Text, nullable=True)
    therapist_observations = Column(Text, nullable=True)
    student_engagement = Column(String(50), nullable=True)
    materials_used = Column(Text, nullable=True)
    
    # Session outcomes
    goals_addressed = Column(Boolean, nullable=False, server_default='0')
    session_quality = Column(String(20), nullable=True)
    follow_up_needed = Column(Boolean, nullable=False, server_default='0')
    follow_up_notes = Column(Text, nullable=True)
    
    # Series tracking
    series_id = Column(String(36), nullable=True, index=True)
    series_metadata = Column(Text, nullable=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(String(100), nullable=True)

    # Relationships
    student = relationship("Student", back_populates="therapy_sessions")
    appointment = relationship("Appointment", back_populates="therapy_session")
    time_block = relationship("TimeBlock", back_populates="therapy_sessions")
    session_goals = relationship("SessionGoal", back_populates="therapy_session", cascade="all, delete-orphan")
    session_objectives = relationship("SessionObjective", back_populates="therapy_session", cascade="all, delete-orphan")
    progress_entries = relationship("ObjectiveProgressEntry", back_populates="therapy_session", cascade="all, delete-orphan")

    @property
    def is_scheduled(self) -> bool:
        """Check if session is linked to an appointment"""
        return self.appointment_id is not None

    @property
    def is_group_session(self) -> bool:
        """Check if session is part of a group/time block"""
        return self.time_block_id is not None

    @property
    def duration_minutes(self) -> int:
        """Calculate actual session duration in minutes"""
        if self.actual_start_time and self.actual_end_time:
            delta = self.actual_end_time - self.actual_start_time
            return int(delta.total_seconds() / 60)
        if self.actual_duration_minutes is not None:
            return self.actual_duration_minutes
        if self.planned_duration_minutes is not None:
            return self.planned_duration_minutes
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def is_active(self) -> bool:
        """Check if session is currently in progress"""
        return self.status == 'in_progress'

    @property
    def is_completed(self) -> bool:
        """Check if session is completed"""
        return self.status == 'completed'

    @property
    def planned_goals_count(self) -> int:
        """Count of planned goals for this session"""
        return len([sg for sg in self.session_goals if sg.planned])

    @property
    def worked_goals_count(self) -> int:
        """Count of goals actually worked on"""
        return len([sg for sg in self.session_goals if sg.worked_on])

    @property
    def planned_objectives_count(self) -> int:
        """Count of planned objectives for this session"""
        return len([so for so in self.session_objectives if so.planned])

    @property
    def worked_objectives_count(self) -> int:
        """Count of objectives actually worked on"""
        return len([so for so in self.session_objectives if so.worked_on])

    @property
    def progress_entries_count(self) -> int:
        """Count of progress entries made during session"""
        return len(self.progress_entries)

    @property
    def is_part_of_series(self) -> bool:
        """Check if session is part of a recurring series"""
        return self.series_id is not None

    @property
    def series_config(self) -> dict:
        """Get the series configuration as a dictionary"""
        if self.series_metadata:
            try:
                return json.loads(self.series_metadata)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_series_config(self, config: dict) -> None:
        """Set the series configuration from a dictionary"""
        if config:
            self.series_metadata = json.dumps(config)
        else:
            self.series_metadata = None
