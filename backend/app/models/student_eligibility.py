from sqlalchemy import Column, Integer, Date, DateTime, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.archive_event import ArchivableMixin


class StudentEligibility(ArchivableMixin, Base):
    """Which disability category a child qualifies under, and since when.

    ARCHIVABLE. `DELETE /api/eligibilities/students/{id}` used to remove the row
    outright, which is the one thing this application no longer does to clinical
    data: an eligibility determination is a legal finding about a child, and
    "we took it off the record" and "it never happened" have to be tellable
    apart. It archives instead -- reversibly, under an event that names who did
    it -- and the student cascade sweeps it along with the goals and sessions.

    A LEAF: nothing hangs off an eligibility, so archiving one archives exactly
    it. See `app/services/archive.py`.
    """

    __tablename__ = "student_eligibilities"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    eligibility_category_id = Column(Integer, ForeignKey('eligibility_categories.id'), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default='0', index=True)
    notes = Column(Text, nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    student = relationship("Student", back_populates="eligibilities")
    eligibility_category = relationship("EligibilityCategory", back_populates="student_eligibilities")

    @property
    def is_active(self) -> bool:
        """Check if this eligibility is currently active (no end date)"""
        return self.end_date is None
