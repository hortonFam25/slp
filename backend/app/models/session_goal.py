from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class SessionGoal(Base):
    __tablename__ = "session_goals"

    id = Column(Integer, primary_key=True, index=True)
    therapy_session_id = Column(Integer, ForeignKey('therapy_sessions.id'), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey('iep_goals.id'), nullable=False, index=True)
    
    # Planning and execution tracking
    planned = Column(Boolean, nullable=False, server_default='1')
    worked_on = Column(Boolean, nullable=False, server_default='0')
    priority = Column(Integer, nullable=True)
    
    # Session-specific goal notes
    pre_session_notes = Column(Text, nullable=True)
    session_notes = Column(Text, nullable=True)
    goal_progress_summary = Column(String(500), nullable=True)
    
    # Goal status for this session
    goal_met = Column(Boolean, nullable=True)
    difficulty_level = Column(String(20), nullable=True)
    student_response = Column(String(50), nullable=True)
    
    # Time tracking
    time_spent_minutes = Column(Integer, nullable=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Ensure one record per session-goal combination
    __table_args__ = (
        UniqueConstraint('therapy_session_id', 'goal_id', name='uq_session_goal'),
    )

    # Relationships
    therapy_session = relationship("TherapySession", back_populates="session_goals")
    goal = relationship("IEPGoal", back_populates="session_goals")

    @property
    def goal_description(self) -> str:
        """Get the goal description"""
        return self.goal.goal_description if self.goal else ""

    @property
    def goal_category(self) -> str:
        """Get the goal category name"""
        return self.goal.goal_category.name if self.goal and self.goal.goal_category else ""

    @property
    def student_id(self) -> int:
        """Get the student ID through the goal"""
        return self.goal.student_id if self.goal else None

    @property
    def was_successful(self) -> bool:
        """Determine if goal work was successful"""
        return (
            self.worked_on and 
            self.goal_met is True and 
            self.student_response in ['engaged', 'motivated']
        )
