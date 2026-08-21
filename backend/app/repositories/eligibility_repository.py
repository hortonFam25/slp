"""Eligibility categories, and the determinations that point at them.

ARCHIVE FILTERING. `StudentEligibility` is archivable; `EligibilityCategory` is
NOT. The distinction is the point: a determination is one child's clinical
record and belongs in the archive, while a category is a shared lookup that
every child's determination points at, and hiding one would silently rewrite
the vocabulary for the whole caseload.

So every read path over `student_eligibilities` here filters
`archived_at IS NULL` unless the caller passes `include_archived=True`, and the
category reads are untouched.

There is no `delete_student_eligibility` any more. `archive_student_eligibility`
is what the DELETE route calls, and it is reversible -- see
`app/services/archive.py`.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.eligibility_category import EligibilityCategory
from app.models.student_eligibility import StudentEligibility
from app.schemas.eligibility import StudentEligibilityCreate, StudentEligibilityUpdate
from app.services import archive as archive_service


class EligibilityRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_all_categories(self, active_only: bool = True) -> List[EligibilityCategory]:
        """Get all eligibility categories"""
        query = self.session.query(EligibilityCategory)
        if active_only:
            query = query.filter(EligibilityCategory.is_active == True)
        return query.order_by(EligibilityCategory.display_order, EligibilityCategory.name).all()

    def get_category_by_id(self, category_id: int) -> Optional[EligibilityCategory]:
        """Get eligibility category by ID"""
        return self.session.query(EligibilityCategory).filter(EligibilityCategory.id == category_id).first()

    def get_student_eligibilities(
        self, student_id: int, include_archived: bool = False
    ) -> List[StudentEligibility]:
        """Get all eligibilities for a student"""
        query = self.session.query(StudentEligibility)\
            .filter(StudentEligibility.student_id == student_id)
        if not include_archived:
            query = query.filter(StudentEligibility.archived_at.is_(None))
        return query\
            .order_by(StudentEligibility.is_primary.desc(), StudentEligibility.start_date.desc())\
            .all()

    def create_student_eligibility(self, payload: StudentEligibilityCreate) -> StudentEligibility:
        """Create a new student eligibility"""
        eligibility = StudentEligibility(
            student_id=payload.student_id,
            eligibility_category_id=payload.eligibility_category_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_primary=payload.is_primary,
            notes=payload.notes
        )
        self.session.add(eligibility)
        self.session.commit()
        self.session.refresh(eligibility)
        return eligibility

    def update_student_eligibility(self, eligibility_id: int, payload: StudentEligibilityUpdate) -> Optional[StudentEligibility]:
        """Update an existing student eligibility.

        An archived row is not updatable: `get_student_eligibility_by_id`
        refuses it, which is what turns an archived id into the same 404 the
        caller used to get after a DELETE.
        """
        eligibility = self.get_student_eligibility_by_id(eligibility_id)
        if not eligibility:
            return None

        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(eligibility, field, value)

        self.session.commit()
        self.session.refresh(eligibility)
        return eligibility

    def archive_student_eligibility(
        self, eligibility_id: int, user_id: int, reason: Optional[str] = None
    ) -> Optional["archive_service.ArchiveEvent"]:
        """Archive one eligibility determination, in place of deleting it.

        Returns None when there is no such active row -- the caller turns that
        into the 404 the DELETE used to return. Raises
        `archive_service.AlreadyArchivedError` for a row that is already
        archived, which the route reports as a 409, exactly as the other seven
        archivable entities do.
        """
        eligibility = self.get_student_eligibility_by_id(
            eligibility_id, include_archived=True
        )
        if not eligibility:
            return None

        return archive_service.archive(
            self.session,
            user_id=user_id,
            entity_type=archive_service.ENTITY_STUDENT_ELIGIBILITY,
            entity_id=eligibility_id,
            reason=reason,
        )

    def get_student_eligibility_by_id(
        self, eligibility_id: int, include_archived: bool = False
    ) -> Optional[StudentEligibility]:
        """Get student eligibility by ID"""
        query = self.session.query(StudentEligibility).filter(
            StudentEligibility.id == eligibility_id
        )
        if not include_archived:
            query = query.filter(StudentEligibility.archived_at.is_(None))
        return query.first()
