from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, text
from sqlalchemy.sql.sqltypes import Numeric
from sqlalchemy.orm import relationship
from app.db.base import Base


class ProgressTracking(Base):
    __tablename__ = "progress_tracking"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey('iep_goals.id'), nullable=False, index=True)
    session_date = Column(Date, nullable=False, index=True)
    data_collection_method = Column(String(100), nullable=True)
    performance_score = Column(Numeric(5, 2), nullable=True)
    performance_percentage = Column(Numeric(5, 2), nullable=True)
    trials_correct = Column(Integer, nullable=True)
    trials_total = Column(Integer, nullable=True)
    qualitative_notes = Column(Text, nullable=True)
    session_duration_minutes = Column(Integer, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    student = relationship("Student", back_populates="progress_tracking")
    goal = relationship("IEPGoal", back_populates="progress_tracking")

    @property
    def success_rate(self) -> float | None:
        """Calculate success rate from trials if available"""
        if self.trials_total and self.trials_total > 0:
            return (self.trials_correct or 0) / self.trials_total * 100
        return None
