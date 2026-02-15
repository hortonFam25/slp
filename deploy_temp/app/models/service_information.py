from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, Text, ForeignKey, text
from sqlalchemy.orm import relationship
from app.db.base import Base


class ServiceInformation(Base):
    __tablename__ = "service_information"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False, index=True)
    service_type_id = Column(Integer, ForeignKey('service_types.id'), nullable=False, index=True)
    frequency_per_week = Column(Integer, nullable=True)
    session_duration_minutes = Column(Integer, nullable=True)
    service_location = Column(String(100), nullable=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1', index=True)
    notes = Column(Text, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))
    modified_date = Column(DateTime, nullable=False, server_default=text('GETDATE()'))

    # Relationships
    student = relationship("Student", back_populates="service_information")
    service_type = relationship("ServiceType", back_populates="service_information")
