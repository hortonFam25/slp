"""Student reads and writes.

ARCHIVE FILTERING. Every list path here excludes archived students unless the
caller asks for them, exactly as it did before -- but the predicate is now
`Student.archived_at IS NULL` rather than `is_archived = 0`. The two agree by
construction (`Student.is_archived` is a hybrid over the timestamp), and the
timestamp is the one the archive service writes.

Two methods deliberately DO see archived students by default, and both would be
bugs if they did not:

* `get_student_by_id` -- the app's student-detail page is how a therapist
  reaches the Unarchive button, so it has always loaded archived students and
  must keep doing so. The parameter exists so the default is a decision rather
  than an accident.
* `get_student_by_uic` -- deduplication. `students.uic` is UNIQUE; a lookup
  that could not see an archived student would report "no such UIC" and then
  fail on the constraint, and a caseload import would offer to re-create a
  child who is sitting in the archive. Archived rows MUST be visible here.
"""

from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.student import Student
from app.models.student_eligibility import StudentEligibility
from app.schemas.student import StudentCreate, StudentUpdate
from app.services import archive as archive_service


class StudentRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _apply_access_filter(query, allowed_student_ids: Optional[list[int]] = None):
        if allowed_student_ids is None:
            return query
        if not allowed_student_ids:
            return query.filter(Student.id == -1)
        return query.filter(Student.id.in_(allowed_student_ids))

    def list_students(
        self,
        enrollment_status: Optional[str] = None,
        include_archived: bool = False,
        allowed_student_ids: Optional[list[int]] = None,
    ) -> List[Student]:
        query = self.session.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager)
        )
        query = self._apply_access_filter(query, allowed_student_ids)

        # Filter out archived students by default
        if not include_archived:
            query = query.filter(Student.archived_at.is_(None))

        if enrollment_status:
            query = query.filter(Student.enrollment_status == enrollment_status)

        return query.order_by(Student.last.asc()).all()

    def get_student_by_id(
        self,
        student_id: int,
        allowed_student_ids: Optional[list[int]] = None,
        include_archived: bool = True,
    ) -> Optional[Student]:
        """One student by id. Archived students ARE returned by default.

        See the module docstring: the detail page is where a therapist
        unarchives, so hiding archived students from a by-id lookup would take
        the Unarchive button away from the only page that shows it.
        """
        student = self.session.query(Student)\
            .options(
                joinedload(Student.eligibilities).joinedload(StudentEligibility.eligibility_category),
                joinedload(Student.school),
                joinedload(Student.teacher),
                joinedload(Student.case_manager)
            )\
            .filter(Student.id == student_id)
        if not include_archived:
            student = student.filter(Student.archived_at.is_(None))
        student = self._apply_access_filter(student, allowed_student_ids).first()

        return student

    def get_student_by_uic(self, uic: str, include_archived: bool = True) -> Optional[Student]:
        """UIC lookup. Archived students ARE returned by default -- deliberately.

        This is the deduplication path (`csv_import_service`,
        `goals_import_service`, the create/update UIC conflict checks) and
        `students.uic` is a UNIQUE column. A lookup blind to the archive would
        turn "this child is already on the caseload, archived" into "no such
        child" followed by an IntegrityError.
        """
        query = self.session.query(Student).filter(Student.uic == uic)
        if not include_archived:
            query = query.filter(Student.archived_at.is_(None))
        return query.first()

    def get_students_by_case_manager(
        self,
        case_manager_id: int,
        include_archived: bool = False,
        allowed_student_ids: Optional[list[int]] = None,
    ) -> List[Student]:
        query = self.session.query(Student).filter(Student.case_manager_id == case_manager_id)
        query = self._apply_access_filter(query, allowed_student_ids)

        # Filter out archived students by default
        if not include_archived:
            query = query.filter(Student.archived_at.is_(None))

        return query.order_by(Student.last.asc()).all()

    def create_student(self, payload: StudentCreate) -> Student:
        student = Student(
            student_alias="",
            first=payload.first,
            last=payload.last,
            uic=payload.uic,
            grade_level=payload.grade_level,
            teacher_id=payload.teacher_id,
            case_manager_id=payload.case_manager_id,
            enrollment_status=payload.enrollment_status or "Active",
            # Goes through the hybrid setter, which writes `archived_at` and
            # keeps the legacy `is_archived` column in step.
            is_archived=payload.is_archived,
            date_of_birth=payload.date_of_birth,
            school_id=payload.school_id,
            # IEP Date Fields
            iep_date=payload.iep_date,
            annual_review_due_date=payload.annual_review_due_date,
            reevaluation_due_date=payload.reevaluation_due_date,
            iep_meeting_date=payload.iep_meeting_date,
            initial_evaluation_date=payload.initial_evaluation_date,
            eligibility_determination_date=payload.eligibility_determination_date
        )
        self.session.add(student)
        self.session.flush()
        student.student_alias = f"student_{student.id}"
        self.session.commit()
        self.session.refresh(student)

        # Load relationships for proper serialization
        student = self.session.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager),
            joinedload(Student.eligibilities)
        ).filter(Student.id == student.id).first()

        return student

    def update_student(
        self,
        student_id: int,
        payload: StudentUpdate,
        allowed_student_ids: Optional[list[int]] = None,
        user_id: Optional[int] = None,
    ) -> Optional[Student]:
        """Update a student, routing `is_archived` through the archive service.

        `StudentUpdate.is_archived` predates the archive framework and the React
        edit form still sends it on every save (it echoes the student's current
        value back). Left as a plain column write it would archive a student
        with NO event and NO cascade: the child would vanish from every list
        while their goals, sessions and appointments stayed active underneath,
        and nothing could restore them because there was no event to restore.

        So a CHANGE to the flag is delegated:

        * ``True`` on an active student  -> `archive_service.archive`, which
          writes the event and stamps the whole cascade.
        * ``False`` on an archived student -> `unarchive_student`, which
          restores that student's event -- the exact inverse, leaving anything
          archived under an older event alone.
        * a value that matches the student's current state -> nothing at all.
          This is the common case (the form echo) and it must not be a 409.

        `user_id` is who the event is recorded against. A caller that omits it
        cannot change the flag: the audit row would have no author, and a
        silent column write is what this method exists to prevent.
        """
        student = self.get_student_by_id(student_id, allowed_student_ids=allowed_student_ids)
        if not student:
            return None

        update_data = payload.dict(exclude_unset=True)

        archive_change: Optional[bool] = None
        if "is_archived" in update_data:
            requested = bool(update_data.pop("is_archived"))
            if requested != (student.archived_at is not None):
                if user_id is None:
                    raise ValueError(
                        "Archiving a student is recorded as an event and needs "
                        "the acting user. Use PUT /api/students/{id}/archive, "
                        "PUT /api/students/{id}/unarchive or DELETE "
                        "/api/students/{id}."
                    )
                archive_change = requested

        # Update fields, handling ID fields properly
        for field, value in update_data.items():
            if field in ['teacher_id', 'case_manager_id']:
                # Handle ID fields - convert empty strings to None
                if value == '' or value is None:
                    setattr(student, field, None)
                else:
                    setattr(student, field, int(value) if isinstance(value, str) else value)
            else:
                setattr(student, field, value)

        self.session.commit()
        self.session.refresh(student)

        # After the ordinary fields, so a failed archive cannot half-apply an
        # edit -- and so the archive event's timestamp follows the edit that
        # accompanied it rather than preceding it.
        if archive_change is True:
            self.archive_student(
                student_id,
                user_id=user_id,
                allowed_student_ids=allowed_student_ids,
            )
        elif archive_change is False:
            self.unarchive_student(
                student_id,
                user_id=user_id,
                allowed_student_ids=allowed_student_ids,
            )
        if archive_change is not None:
            return self.get_student_by_id(
                student_id, allowed_student_ids=allowed_student_ids
            )
        return student

    def archive_student(
        self,
        student_id: int,
        user_id: int,
        reason: Optional[str] = None,
        allowed_student_ids: Optional[list[int]] = None,
    ) -> Optional[Student]:
        """Archive a student and everything under them, under one event.

        Thin delegation to `app.services.archive`: the cascade, the event row
        and the "only stamp active rows" rule live there, so this method and the
        DELETE route and the MCP tool cannot drift apart.

        Returns None when the student does not exist or is out of the caller's
        access scope. Raises `archive_service.AlreadyArchivedError` when the
        student is already archived -- see that module for why a silent no-op is
        the wrong answer.
        """
        student = self.get_student_by_id(student_id, allowed_student_ids=allowed_student_ids)
        if not student:
            return None

        archive_service.archive(
            self.session,
            user_id=user_id,
            entity_type=archive_service.ENTITY_STUDENT,
            entity_id=student_id,
            reason=reason,
        )
        return self.get_student_by_id(student_id, allowed_student_ids=allowed_student_ids)

    def unarchive_student(
        self,
        student_id: int,
        user_id: int,
        allowed_student_ids: Optional[list[int]] = None,
    ) -> Optional[Student]:
        """Unarchive a student, restoring the whole event they were archived by.

        A student row only ever appears in a cascade as its ROOT, so the event
        on the row is the event whose restore is the exact inverse of the
        archive that hid them -- their goals, sessions and appointments come back
        with them, minus anything that was already archived beforehand.

        A student archived before archive events existed (the `is_archived`
        backfill in a1c4e8b60d37) has no event to restore, so the flags are
        cleared directly. Same for one whose event was somehow already restored.
        """
        student = self.get_student_by_id(student_id, allowed_student_ids=allowed_student_ids)
        if not student:
            return None

        event_id = student.archive_event_id
        if event_id is not None:
            event = archive_service.get_event(self.session, event_id)
            if event.restored_at is None:
                archive_service.restore(self.session, user_id=user_id, event_id=event_id)
                return self.get_student_by_id(
                    student_id, allowed_student_ids=allowed_student_ids
                )

        # Legacy / already-restored event: clear the flags in place. The hybrid
        # setter drops `archived_at`, `archive_event_id` and the old boolean
        # together.
        student.is_archived = False
        self.session.commit()
        self.session.refresh(student)
        return student

    def get_archived_students(self, allowed_student_ids: Optional[list[int]] = None) -> List[Student]:
        """Get all archived students"""
        query = self.session.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager),
        ).filter(Student.archived_at.isnot(None))
        query = self._apply_access_filter(query, allowed_student_ids)
        return query.order_by(Student.last.asc()).all()
