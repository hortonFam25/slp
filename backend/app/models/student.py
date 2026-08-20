from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, case, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.archive_event import ArchivableMixin


class Student(ArchivableMixin, Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_alias = Column(String(64), unique=True, nullable=False, index=True)
    first = Column(String(100), nullable=False)
    last = Column(String(100), nullable=False)
    uic = Column(String(50), unique=True, nullable=True, index=True)
    grade_level = Column(String(35), nullable=True, index=True)
    enrollment_status = Column(String(20), nullable=False, server_default='Active', index=True)
    # The ORIGINAL archive flag, from revision 8f054481089d. Still a real
    # column, still indexed, still what a pre-existing SQL view or report would
    # read -- but no longer the truth. `archived_at` is, and the hybrid below
    # keeps this column in lockstep so the two can never disagree. Mapped under
    # a private name so the public `is_archived` can be the hybrid; the column
    # in the database is still called `is_archived`.
    _is_archived = Column("is_archived", Boolean, nullable=False, server_default='0', index=True)
    date_of_birth = Column(Date, nullable=True)
    
    # IEP Date Fields
    iep_date = Column(Date, nullable=True, index=True)
    annual_review_due_date = Column(Date, nullable=True, index=True)
    reevaluation_due_date = Column(Date, nullable=True, index=True)
    iep_meeting_date = Column(Date, nullable=True)
    initial_evaluation_date = Column(Date, nullable=True)
    eligibility_determination_date = Column(Date, nullable=True)
    
    # School assignment
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=True, index=True)
    
    # Teacher and case manager assignments (new relationship-based approach)
    teacher_id = Column(Integer, ForeignKey('teachers.id'), nullable=True, index=True)
    case_manager_id = Column(Integer, ForeignKey('teachers.id'), nullable=True, index=True)
    
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    service_information = relationship("ServiceInformation", back_populates="student")
    iep_goals = relationship("IEPGoal", back_populates="student")
    progress_tracking = relationship("ProgressTracking", back_populates="student")
    assessment_data = relationship("AssessmentData", back_populates="student")
    eligibilities = relationship("StudentEligibility", back_populates="student")
    school = relationship("School", back_populates="students")
    teacher_assignments = relationship("StudentTeacherAssignment", back_populates="student")
    appointments = relationship("Appointment", back_populates="student")
    block_assignments = relationship("BlockAssignment", back_populates="student")
    therapy_sessions = relationship("TherapySession", back_populates="student")
    activity_assignments = relationship("ActivityStudentAssignment", back_populates="student")
    
    # New teacher and case manager relationships
    teacher = relationship("Teacher", foreign_keys=[teacher_id], back_populates="students_as_teacher")
    case_manager = relationship("Teacher", foreign_keys=[case_manager_id], back_populates="students_as_case_manager")

    @hybrid_property
    def is_archived(self) -> bool:
        """Archived-ness, derived from `archived_at`, spelled the old way.

        The REST payload (`StudentRead.is_archived`), the React app and every
        caller written before the archive framework all read this name, so it
        stays -- as a view over the timestamp rather than as a second fact that
        can drift from it.
        """
        return self.archived_at is not None

    @is_archived.expression
    def is_archived(cls):  # noqa: N805 - SQLAlchemy hybrid convention
        """The SQL form, as a CASE rather than as a bare `IS NOT NULL`.

        `Student.is_archived == False` has to compile on SQL Server, which has
        no boolean type: comparing a predicate to a literal there is a syntax
        error, while comparing `CASE WHEN ... THEN 1 ELSE 0 END` to 0 is not.
        New code should filter on `Student.archived_at.is_(None)` directly;
        this exists so that old code and old saved queries keep working.
        """
        return case((cls.archived_at.isnot(None), True), else_=False)

    @is_archived.setter
    def is_archived(self, value: bool) -> None:
        """Writing the old flag writes the new truth.

        Setting True on an already-archived student is a no-op on the
        timestamp: it must not silently re-date an archive, and it must not
        detach the row from the ArchiveEvent that owns it.

        Setting False is the legacy unarchive -- it clears the timestamp AND the
        event link, because a row that is active must not claim membership in an
        archive event (a later restore of that event would otherwise try to
        re-clear a row it no longer owns). Going through
        `app.services.archive.restore` is the supported way to reverse an
        archive; this path exists for `StudentUpdate(is_archived=False)`, which
        the app has always allowed.
        """
        if value:
            if self.archived_at is None:
                self.archived_at = datetime.utcnow()
            self._is_archived = True
        else:
            self.archived_at = None
            self.archive_event_id = None
            self._is_archived = False

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"

    @property
    def alias(self) -> str:
        return self.student_alias or f"student_{self.id}"
    
    @property
    def is_active(self) -> bool:
        """Check if student is active (not archived)"""
        return not self.is_archived
    
    @property
    def is_annual_review_due(self) -> bool:
        """Check if annual review is due or overdue"""
        if not self.annual_review_due_date:
            return False
        from datetime import date
        return date.today() >= self.annual_review_due_date
    
    @property
    def is_reevaluation_due(self) -> bool:
        """Check if re-evaluation is due or overdue"""
        if not self.reevaluation_due_date:
            return False
        from datetime import date
        return date.today() >= self.reevaluation_due_date
    
    @property
    def days_until_annual_review(self) -> int | None:
        """Days until annual review due date (negative if overdue)"""
        if not self.annual_review_due_date:
            return None
        from datetime import date
        return (self.annual_review_due_date - date.today()).days
    
    @property
    def days_until_reevaluation(self) -> int | None:
        """Days until re-evaluation due date (negative if overdue)"""
        if not self.reevaluation_due_date:
            return None
        from datetime import date
        return (self.reevaluation_due_date - date.today()).days
    
    @property
    def current_teachers(self) -> list:
        """List of teachers currently assigned to this student"""
        return [assignment.teacher for assignment in self.teacher_assignments 
                if assignment.end_date is None and assignment.teacher.is_active]
    
    @property
    def primary_teacher(self):
        """Primary teacher assignment if any"""
        primary_assignments = [assignment for assignment in self.teacher_assignments 
                             if assignment.is_primary and assignment.end_date is None]
        return primary_assignments[0].teacher if primary_assignments else None
    
    @property
    def school_name(self) -> str:
        """School name or 'Not Assigned'"""
        return self.school.name if self.school else "Not Assigned"


