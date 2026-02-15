from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.student import Student
from app.models.student_eligibility import StudentEligibility
from app.schemas.student import StudentCreate, StudentUpdate


class StudentRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_students(self, enrollment_status: Optional[str] = None, include_archived: bool = False) -> List[Student]:
        query = self.session.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager)
        )
        
        # Filter out archived students by default
        if not include_archived:
            query = query.filter(Student.is_archived == False)
            
        if enrollment_status:
            query = query.filter(Student.enrollment_status == enrollment_status)
            
        return query.order_by(Student.last.asc()).all()

    def get_student_by_id(self, student_id: int) -> Optional[Student]:
        student = self.session.query(Student)\
            .options(
                joinedload(Student.eligibilities).joinedload(StudentEligibility.eligibility_category),
                joinedload(Student.school),
                joinedload(Student.teacher),
                joinedload(Student.case_manager)
            )\
            .filter(Student.id == student_id).first()
        
        return student

    def get_student_by_uic(self, uic: str) -> Optional[Student]:
        return self.session.query(Student).filter(Student.uic == uic).first()

    def get_students_by_case_manager(self, case_manager_id: int, include_archived: bool = False) -> List[Student]:
        query = self.session.query(Student).filter(Student.case_manager_id == case_manager_id)
        
        # Filter out archived students by default
        if not include_archived:
            query = query.filter(Student.is_archived == False)
            
        return query.order_by(Student.last.asc()).all()

    def create_student(self, payload: StudentCreate) -> Student:
        student = Student(
            first=payload.first,
            last=payload.last,
            uic=payload.uic,
            grade_level=payload.grade_level,
            teacher_id=payload.teacher_id,
            case_manager_id=payload.case_manager_id,
            enrollment_status=payload.enrollment_status or "Active",
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

    def update_student(self, student_id: int, payload: StudentUpdate) -> Optional[Student]:
        student = self.get_student_by_id(student_id)
        if not student:
            return None
        
        update_data = payload.dict(exclude_unset=True)
        
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
        return student

    def delete_student(self, student_id: int) -> bool:
        student = self.get_student_by_id(student_id)
        if not student:
            return False
        
        self.session.delete(student)
        self.session.commit()
        return True

    def archive_student(self, student_id: int) -> Optional[Student]:
        """Archive a student (hide from active lists but preserve data)"""
        student = self.get_student_by_id(student_id)
        if not student:
            return None
        
        student.is_archived = True
        self.session.commit()
        self.session.refresh(student)
        return student

    def unarchive_student(self, student_id: int) -> Optional[Student]:
        """Unarchive a student (restore to active lists)"""
        student = self.get_student_by_id(student_id)
        if not student:
            return None
        
        student.is_archived = False
        self.session.commit()
        self.session.refresh(student)
        return student

    def get_archived_students(self) -> List[Student]:
        """Get all archived students"""
        return self.session.query(Student).filter(
            Student.is_archived == True
        ).order_by(Student.last.asc()).all()


