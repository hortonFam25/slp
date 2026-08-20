from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ObjectiveProgressEntry(Base):
    __tablename__ = "objective_progress_entries"

    id = Column(Integer, primary_key=True, index=True)
    objective_id = Column(Integer, ForeignKey('goal_objectives.id'), nullable=False, index=True)
    therapy_session_id = Column(Integer, ForeignKey('therapy_sessions.id'), nullable=True, index=True)
    progress_date = Column(Date, nullable=False, index=True)
    progress_on_objective = Column(String(100), nullable=True)
    progress_comments = Column(Text, nullable=True)
    therapist_initials = Column(String(10), nullable=True)
    session_type = Column(String(50), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    objective = relationship("GoalObjective", back_populates="progress_entries")
    therapy_session = relationship("TherapySession", back_populates="progress_entries")

    @property
    def student_id(self) -> int:
        """Get the student ID through the objective's goal"""
        return self.objective.goal.student_id if self.objective and self.objective.goal else None

    @property
    def goal_id(self) -> int:
        """Get the goal ID through the objective"""
        return self.objective.goal_id if self.objective else None

    @property
    def is_session_linked(self) -> bool:
        """Check if this progress entry is linked to a therapy session"""
        return self.therapy_session_id is not None

    @property
    def session_date(self):
        """Get the session date if linked to a therapy session"""
        return self.therapy_session.session_date if self.therapy_session else None
