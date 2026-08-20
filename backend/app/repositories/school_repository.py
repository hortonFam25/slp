from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, and_, or_, func
from datetime import date

from app.models.school import School
from app.models.teacher_school_assignment import TeacherSchoolAssignment
from app.models.student import Student


class SchoolRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_school(self, school_data: Dict[str, Any]) -> School:
        """Create a new school"""
        school = School(**school_data)
        self.db.add(school)
        self.db.commit()
        self.db.refresh(school)
        return school

    def get_school_by_id(self, school_id: int) -> Optional[School]:
        """Get school by ID with related data"""
        return self.db.query(School).options(
            joinedload(School.students),
            joinedload(School.teacher_assignments)
        ).filter(School.id == school_id).first()

    def get_school_by_name(self, name: str) -> Optional[School]:
        """Get school by exact name match"""
        return self.db.query(School).filter(School.name == name).first()

    def list_schools(
        self,
        is_active: Optional[bool] = None,
        district: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[School]:
        """List schools with optional filters"""
        query = self.db.query(School)

        # Apply filters
        if is_active is not None:
            query = query.filter(School.is_active == is_active)

        if district:
            query = query.filter(School.district.ilike(f"%{district}%"))

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    School.name.ilike(search_term),
                    School.district.ilike(search_term),
                    School.principal_name.ilike(search_term),
                    School.contact_person.ilike(search_term)
                )
            )

        # Order by name and apply pagination
        query = query.order_by(asc(School.name))
        return query.offset(skip).limit(limit).all()

    def update_school(self, school_id: int, update_data: Dict[str, Any]) -> Optional[School]:
        """Update school information"""
        school = self.db.query(School).filter(School.id == school_id).first()
        if not school:
            return None

        for field, value in update_data.items():
            if hasattr(school, field):
                setattr(school, field, value)

        self.db.commit()
        self.db.refresh(school)
        return school

    def delete_school(self, school_id: int) -> bool:
        """Soft delete school (mark as inactive)"""
        school = self.db.query(School).filter(School.id == school_id).first()
        if not school:
            return False

        school.is_active = False
        self.db.commit()
        return True

    def get_schools_by_district(self, district: str) -> List[School]:
        """Get all schools in a specific district"""
        return self.db.query(School).filter(
            School.district.ilike(f"%{district}%"),
            School.is_active == True
        ).order_by(asc(School.name)).all()

    def get_active_schools_summary(self) -> List[School]:
        """Get summary of all active schools for dropdowns"""
        return self.db.query(School).filter(
            School.is_active == True
        ).order_by(asc(School.name)).all()

    def get_school_statistics(self, school_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a school"""
        school = self.get_school_by_id(school_id)
        if not school:
            return {}

        # Count active students. AGGREGATE DECISION: archived students are
        # excluded -- "how many children does this school have on the caseload"
        # is a question about the working roster, not about the whole record.
        active_students = self.db.query(Student).filter(
            Student.school_id == school_id,
            Student.enrollment_status == 'Active',
            Student.archived_at.is_(None)
        ).count()

        # Count active teachers (current assignments)
        active_teachers = self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.school_id == school_id,
            TeacherSchoolAssignment.end_date.is_(None)
        ).count()

        # Count students by grade level
        grade_distribution = self.db.query(
            Student.grade_level,
            func.count(Student.id).label('count')
        ).filter(
            Student.school_id == school_id,
            Student.enrollment_status == 'Active',
            Student.archived_at.is_(None)
        ).group_by(Student.grade_level).all()

        return {
            'school_id': school_id,
            'school_name': school.name,
            'active_students': active_students,
            'active_teachers': active_teachers,
            'grade_distribution': [
                {'grade': grade or 'Unknown', 'count': count}
                for grade, count in grade_distribution
            ]
        }
