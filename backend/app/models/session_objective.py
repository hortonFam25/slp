from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, Numeric, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class SessionObjective(Base):
    __tablename__ = "session_objectives"

    id = Column(Integer, primary_key=True, index=True)
    therapy_session_id = Column(Integer, ForeignKey('therapy_sessions.id'), nullable=False, index=True)
    objective_id = Column(Integer, ForeignKey('goal_objectives.id'), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey('iep_goals.id'), nullable=False, index=True)
    
    # Planning and execution tracking
    planned = Column(Boolean, nullable=False, server_default='1')
    worked_on = Column(Boolean, nullable=False, server_default='0')
    priority = Column(Integer, nullable=True)
    
    # Session-specific objective notes
    pre_session_notes = Column(Text, nullable=True)
    session_notes = Column(Text, nullable=True)
    
    # Performance data (mirrors progress entry structure)
    trials_attempted = Column(Integer, nullable=True)
    trials_correct = Column(Integer, nullable=True)
    accuracy_percentage = Column(Numeric(5, 2), nullable=True)
    independence_level = Column(String(50), nullable=True)
    
    # Objective-specific tracking
    objective_met = Column(Boolean, nullable=True)
    progress_rating = Column(String(20), nullable=True)
    prompt_level = Column(String(50), nullable=True)
    
    # Time and engagement
    time_spent_minutes = Column(Integer, nullable=True)
    student_engagement = Column(String(20), nullable=True)
    
    # Data collection method
    data_collection_method = Column(String(100), nullable=True)
    
    # Metadata
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Ensure one record per session-objective combination
    __table_args__ = (
        UniqueConstraint('therapy_session_id', 'objective_id', name='uq_session_objective'),
    )

    # Relationships
    therapy_session = relationship("TherapySession", back_populates="session_objectives")
    objective = relationship("GoalObjective", back_populates="session_objectives")
    goal = relationship("IEPGoal", back_populates="session_objectives")

    @property
    def objective_description(self) -> str:
        """Get the objective description"""
        return self.objective.objective_description if self.objective else ""

    @property
    def goal_description(self) -> str:
        """Get the parent goal description"""
        return self.goal.goal_description if self.goal else ""

    @property
    def success_rate(self) -> float:
        """Calculate success rate from trials"""
        if self.trials_attempted and self.trials_attempted > 0:
            return (self.trials_correct or 0) / self.trials_attempted * 100
        return self.accuracy_percentage or 0.0

    @property
    def was_successful(self) -> bool:
        """Determine if objective work was successful"""
        return (
            self.worked_on and 
            (self.objective_met is True or self.success_rate >= 80)
        )

    @property
    def needs_more_practice(self) -> bool:
        """Determine if objective needs more practice"""
        return (
            self.worked_on and 
            self.success_rate < 70 and 
            self.progress_rating in ['no_progress', 'minimal']
        )

    @property
    def student_id(self) -> int:
        """Get the student ID through the objective's goal"""
        return self.objective.goal.student_id if self.objective and self.objective.goal else None
