from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class GoalCategory(Base):
    __tablename__ = "goal_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1')
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    iep_goals = relationship("IEPGoal", back_populates="goal_category")
