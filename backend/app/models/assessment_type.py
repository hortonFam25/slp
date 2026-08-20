from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class AssessmentType(Base):
    __tablename__ = "assessment_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1')
    created_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    assessment_data = relationship("AssessmentData", back_populates="assessment_type")
