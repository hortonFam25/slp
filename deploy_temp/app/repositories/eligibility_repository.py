from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.eligibility_category import EligibilityCategory
from app.models.student_eligibility import StudentEligibility
from app.schemas.eligibility import StudentEligibilityCreate, StudentEligibilityUpdate


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

    def get_student_eligibilities(self, student_id: int) -> List[StudentEligibility]:
        """Get all eligibilities for a student"""
        return self.session.query(StudentEligibility)\
            .filter(StudentEligibility.student_id == student_id)\
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
        """Update an existing student eligibility"""
        eligibility = self.session.query(StudentEligibility).filter(StudentEligibility.id == eligibility_id).first()
        if not eligibility:
            return None

        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(eligibility, field, value)

        self.session.commit()
        self.session.refresh(eligibility)
        return eligibility

    def delete_student_eligibility(self, eligibility_id: int) -> bool:
        """Delete a student eligibility"""
        eligibility = self.session.query(StudentEligibility).filter(StudentEligibility.id == eligibility_id).first()
        if not eligibility:
            return False

        self.session.delete(eligibility)
        self.session.commit()
        return True

    def get_student_eligibility_by_id(self, eligibility_id: int) -> Optional[StudentEligibility]:
        """Get student eligibility by ID"""
        return self.session.query(StudentEligibility).filter(StudentEligibility.id == eligibility_id).first()
