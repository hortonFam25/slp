from sqlalchemy import Column, Integer, Date, DateTime, Boolean, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class StudentEligibility(Base):
    __tablename__ = "student_eligibilities"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    eligibility_category_id = Column(Integer, ForeignKey('eligibility_categories.id'), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default='0', index=True)
    notes = Column(Text, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    student = relationship("Student", back_populates="eligibilities")
    eligibility_category = relationship("EligibilityCategory", back_populates="student_eligibilities")

    @property
    def is_active(self) -> bool:
        """Check if this eligibility is currently active (no end date)"""
        return self.end_date is None
