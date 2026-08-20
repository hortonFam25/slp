from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.archive_event import ArchivableMixin


class IEPGoal(ArchivableMixin, Base):
    __tablename__ = "iep_goals"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    goal_category_id = Column(Integer, ForeignKey('goal_categories.id'), nullable=False, index=True)
    goal_number = Column(String(20), nullable=True, index=True)
    goal_description = Column(Text, nullable=False)
    target_behavior = Column(Text, nullable=True)
    baseline_data = Column(String(500), nullable=True)
    target_criteria = Column(String(500), nullable=False)
    goal_status = Column(String(20), nullable=False, server_default='Active', index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    mastery_date = Column(Date, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="iep_goals")
    goal_category = relationship("GoalCategory", back_populates="iep_goals")
    progress_tracking = relationship("ProgressTracking", back_populates="goal")
    objectives = relationship("GoalObjective", back_populates="goal", cascade="all, delete-orphan")
    session_goals = relationship("SessionGoal", back_populates="goal", cascade="all, delete-orphan")
    session_objectives = relationship("SessionObjective", back_populates="goal", cascade="all, delete-orphan")
