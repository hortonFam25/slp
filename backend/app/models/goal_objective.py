from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class GoalObjective(Base):
    __tablename__ = "goal_objectives"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey('iep_goals.id'), nullable=False, index=True)
    objective_number = Column(Integer, nullable=False)
    objective_description = Column(Text, nullable=False)
    progress_status = Column(String(50), nullable=True)
    schedule_frequency = Column(String(50), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Constraints
    __table_args__ = (
        UniqueConstraint('goal_id', 'objective_number', name='uq_goal_objective'),
        CheckConstraint('objective_number >= 1 AND objective_number <= 10', name='ck_objective_number_range'),
    )

    # Relationships
    goal = relationship("IEPGoal", back_populates="objectives")
    progress_entries = relationship("ObjectiveProgressEntry", back_populates="objective", cascade="all, delete-orphan")
    session_objectives = relationship("SessionObjective", back_populates="objective", cascade="all, delete-orphan")

    @property
    def latest_progress_entry(self):
        """Get the most recent progress entry for this objective"""
        if self.progress_entries:
            return max(self.progress_entries, key=lambda x: x.progress_date)
        return None

    @property
    def progress_count(self) -> int:
        """Count of progress entries for this objective"""
        return len(self.progress_entries) if self.progress_entries else 0
