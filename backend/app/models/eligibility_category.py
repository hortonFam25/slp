from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class EligibilityCategory(Base):
    __tablename__ = "eligibility_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(20), nullable=True, unique=True, index=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1', index=True)
    display_order = Column(Integer, nullable=True, index=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    student_eligibilities = relationship("StudentEligibility", back_populates="eligibility_category")
