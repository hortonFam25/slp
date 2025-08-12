from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, text
from sqlalchemy.orm import relationship
import json
from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=True, index=True)
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True, index=True)
    time_block_id = Column(Integer, ForeignKey('time_blocks.id'), nullable=True, index=True)
    
    # Time scheduling
    start_datetime = Column(DateTime, nullable=False, index=True)
    end_datetime = Column(DateTime, nullable=False, index=True)
    
    # Appointment details
    appointment_type = Column(String(50), nullable=False, server_default='individual', index=True)
    status = Column(String(20), nullable=False, server_default='scheduled', index=True)
    location = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Session tracking
    therapy_session_completed = Column(Boolean, nullable=False, server_default='0')
    session_notes = Column(Text, nullable=True)
    
    # Series tracking
    series_id = Column(String(36), nullable=True, index=True)
    series_metadata = Column(Text, nullable=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    created_by = Column(String(100), nullable=True)

    # Relationships
    student = relationship("Student", back_populates="appointments")
    teacher = relationship("Teacher", back_populates="appointments")
    school = relationship("School", back_populates="appointments")
    time_block = relationship("TimeBlock", back_populates="appointments")
    therapy_session = relationship("TherapySession", back_populates="appointment", uselist=False)

    @property
    def duration_minutes(self) -> int:
        """Calculate appointment duration in minutes"""
        if self.start_datetime and self.end_datetime:
            delta = self.end_datetime - self.start_datetime
            return int(delta.total_seconds() / 60)
        return 0

    @property
    def is_past(self) -> bool:
        """Check if appointment is in the past"""
        from datetime import datetime
        return self.end_datetime < datetime.now() if self.end_datetime else False

    @property
    def can_start_session(self) -> bool:
        """Check if therapy session can be started"""
        return (
            self.status == 'scheduled' and 
            not self.therapy_session_completed and
            self.appointment_type in ['individual', 'group'] and
            not self.has_therapy_session
        )

    @property
    def has_therapy_session(self) -> bool:
        """Check if appointment has an associated therapy session"""
        return self.therapy_session is not None

    @property
    def session_status(self) -> str:
        """Get the therapy session status if exists"""
        return self.therapy_session.status if self.therapy_session else 'none'
    
    @property
    def is_group_appointment(self) -> bool:
        """Check if appointment is part of a time block/group"""
        return self.time_block_id is not None

    @property
    def is_part_of_series(self) -> bool:
        """Check if appointment is part of a recurring series"""
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
