from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class AssessmentData(Base):
    __tablename__ = "assessment_data"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    assessment_type_id = Column(Integer, ForeignKey('assessment_types.id'), nullable=False, index=True)
    assessment_name = Column(String(200), nullable=False)
    assessment_date = Column(Date, nullable=False, index=True)
    standard_score = Column(Integer, nullable=True)
    percentile_rank = Column(Integer, nullable=True)
    age_equivalent = Column(String(20), nullable=True)
    grade_equivalent = Column(String(20), nullable=True)
    raw_score = Column(Integer, nullable=True)
    scaled_score = Column(Integer, nullable=True)
    results_summary = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    student = relationship("Student", back_populates="assessment_data")
    assessment_type = relationship("AssessmentType", back_populates="assessment_data")
