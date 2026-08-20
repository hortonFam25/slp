from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, and_, or_
from datetime import date

from app.models.teacher import Teacher
from app.models.teacher_school_assignment import TeacherSchoolAssignment
from app.models.student_teacher_assignment import StudentTeacherAssignment
from app.models.role import Role
from app.models.teacher_role import TeacherRole
from app.models.school import School
from app.models.student import Student


class TeacherRepository:
    def __init__(self, db: Session):
        self.db = db

    def _get_active_roles_by_ids(self, role_ids: List[int]) -> List[Role]:
        if not role_ids:
            return []

        roles = self.db.query(Role).filter(
            Role.id.in_(role_ids),
            Role.is_active == True
        ).all()

        if len(roles) != len(set(role_ids)):
            raise ValueError("One or more role IDs are invalid or inactive")

        return roles

    def create_teacher(self, teacher_data: Dict[str, Any]) -> Teacher:
        """Create a new teacher"""
        role_ids = teacher_data.pop("role_ids", [])
        self._get_active_roles_by_ids(role_ids)

        teacher = Teacher(**teacher_data)
        teacher.teacher_roles = [TeacherRole(role_id=role_id) for role_id in role_ids]
        self.db.add(teacher)
        self.db.commit()
        self.db.refresh(teacher)
        return teacher

    def get_teacher_by_id(self, teacher_id: int) -> Optional[Teacher]:
        """Get teacher by ID with related data"""
        return self.db.query(Teacher).options(
            joinedload(Teacher.school_assignments).joinedload(TeacherSchoolAssignment.school),
            joinedload(Teacher.student_assignments).joinedload(StudentTeacherAssignment.student),
            joinedload(Teacher.teacher_roles).joinedload(TeacherRole.role)
        ).filter(Teacher.id == teacher_id).first()

    def get_teacher_by_email(self, email: str) -> Optional[Teacher]:
        """Get teacher by email"""
        return self.db.query(Teacher).filter(Teacher.email == email).first()

    def list_teachers(
        self,
        is_active: Optional[bool] = None,
        school_id: Optional[int] = None,
        role_id: Optional[int] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Teacher]:
        """List teachers with optional filters"""
        query = self.db.query(Teacher).options(
            joinedload(Teacher.school_assignments).joinedload(TeacherSchoolAssignment.school),
            joinedload(Teacher.teacher_roles).joinedload(TeacherRole.role),
            joinedload(Teacher.students_as_teacher).joinedload(Student.school),
            joinedload(Teacher.students_as_case_manager).joinedload(Student.school)
        )

        # Apply filters
        if is_active is not None:
            query = query.filter(Teacher.is_active == is_active)

        if school_id:
            query = query.outerjoin(
                TeacherSchoolAssignment,
                and_(
                    TeacherSchoolAssignment.teacher_id == Teacher.id,
                    TeacherSchoolAssignment.end_date.is_(None),
                )
            ).filter(
                or_(
                    TeacherSchoolAssignment.school_id == school_id,
                    Teacher.students_as_teacher.any(
                        and_(Student.school_id == school_id, Student.enrollment_status == "Active", Student.archived_at.is_(None))
                    ),
                    Teacher.students_as_case_manager.any(
                        and_(Student.school_id == school_id, Student.enrollment_status == "Active", Student.archived_at.is_(None))
                    )
                )
            )

        if role_id:
            query = query.join(TeacherRole).filter(TeacherRole.role_id == role_id)

        if department:
            query = query.filter(Teacher.department.ilike(f"%{department}%"))

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Teacher.first_name.ilike(search_term),
                    Teacher.last_name.ilike(search_term),
                    Teacher.email.ilike(search_term),
                    Teacher.title.ilike(search_term),
                    Teacher.department.ilike(search_term)
                )
            )

        # Order by last name, first name and apply pagination
        query = query.distinct().order_by(asc(Teacher.last_name), asc(Teacher.first_name))
        return query.offset(skip).limit(limit).all()

    def update_teacher(self, teacher_id: int, update_data: Dict[str, Any]) -> Optional[Teacher]:
        """Update teacher information"""
        teacher = self.db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            return None

        role_ids = update_data.pop("role_ids", None)
        if role_ids is not None:
            self._get_active_roles_by_ids(role_ids)
            teacher.teacher_roles = [TeacherRole(role_id=role_id) for role_id in role_ids]

        for field, value in update_data.items():
            if hasattr(teacher, field):
                setattr(teacher, field, value)

        self.db.commit()
        self.db.refresh(teacher)
        return teacher

    def delete_teacher(self, teacher_id: int) -> bool:
        """Soft delete teacher (mark as inactive)"""
        teacher = self.db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            return False

        teacher.is_active = False
        self.db.commit()
        return True

    def get_teachers_by_school(self, school_id: int, current_only: bool = True) -> List[Teacher]:
        """Get teachers assigned to a specific school"""
        query = self.db.query(Teacher).join(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.school_id == school_id,
            Teacher.is_active == True
        )

        if current_only:
            query = query.filter(TeacherSchoolAssignment.end_date.is_(None))

        return query.order_by(asc(Teacher.last_name), asc(Teacher.first_name)).all()

    def get_active_teachers_summary(self) -> List[Teacher]:
        """Get summary of all active teachers for dropdowns"""
        return self.db.query(Teacher).filter(
            Teacher.is_active == True
        ).options(
            joinedload(Teacher.teacher_roles).joinedload(TeacherRole.role),
            joinedload(Teacher.students_as_teacher).joinedload(Student.school),
            joinedload(Teacher.students_as_case_manager).joinedload(Student.school)
        ).order_by(asc(Teacher.last_name), asc(Teacher.first_name)).all()

    def list_roles(self, active_only: bool = True) -> List[Role]:
        query = self.db.query(Role)
        if active_only:
            query = query.filter(Role.is_active == True)
        return query.order_by(asc(Role.name)).all()

    def assign_teacher_to_school(self, assignment_data: Dict[str, Any]) -> TeacherSchoolAssignment:
        """Create a teacher-school assignment"""
        assignment = TeacherSchoolAssignment(**assignment_data)
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def assign_student_to_teacher(self, assignment_data: Dict[str, Any]) -> StudentTeacherAssignment:
        """Create a student-teacher assignment"""
        assignment = StudentTeacherAssignment(**assignment_data)
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def end_teacher_school_assignment(self, assignment_id: int, end_date: date) -> bool:
        """End a teacher-school assignment"""
        assignment = self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            return False

        assignment.end_date = end_date
        self.db.commit()
        return True

    def end_student_teacher_assignment(self, assignment_id: int, end_date: date) -> bool:
        """End a student-teacher assignment"""
        assignment = self.db.query(StudentTeacherAssignment).filter(
            StudentTeacherAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            return False

        assignment.end_date = end_date
        self.db.commit()
        return True

    def get_teacher_statistics(self, teacher_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a teacher"""
        teacher = self.get_teacher_by_id(teacher_id)
        if not teacher:
            return {}

        # Count current students
        current_students = self.db.query(StudentTeacherAssignment).filter(
            StudentTeacherAssignment.teacher_id == teacher_id,
            StudentTeacherAssignment.end_date.is_(None)
        ).count()

        # Count current schools
        current_schools = self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.teacher_id == teacher_id,
            TeacherSchoolAssignment.end_date.is_(None)
        ).count()

        # Get subject distribution
        subject_distribution = self.db.query(
            StudentTeacherAssignment.subject,
            self.db.func.count(StudentTeacherAssignment.id).label('count')
        ).filter(
            StudentTeacherAssignment.teacher_id == teacher_id,
            StudentTeacherAssignment.end_date.is_(None)
        ).group_by(StudentTeacherAssignment.subject).all()

        return {
            'teacher_id': teacher_id,
            'teacher_name': teacher.full_name,
            'current_students': current_students,
            'current_schools': current_schools,
            'subject_distribution': [
                {'subject': subject or 'General', 'count': count}
                for subject, count in subject_distribution
            ]
        }

    def get_teacher_school_assignments(self, teacher_id: int) -> List[TeacherSchoolAssignment]:
        """Get all school assignments for a teacher"""
        return self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.teacher_id == teacher_id
        ).all()

    def update_teacher_school_assignment(self, assignment_id: int, assignment_data: Dict[str, Any]) -> Optional[TeacherSchoolAssignment]:
        """Update a teacher-school assignment"""
        assignment = self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            return None

        # Update fields
        for field, value in assignment_data.items():
            if hasattr(assignment, field):
                setattr(assignment, field, value)

        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def delete_teacher_school_assignment(self, assignment_id: int) -> bool:
        """Delete a teacher-school assignment"""
        assignment = self.db.query(TeacherSchoolAssignment).filter(
            TeacherSchoolAssignment.id == assignment_id
        ).first()
        
        if not assignment:
            return False

        self.db.delete(assignment)
        self.db.commit()
        return True
