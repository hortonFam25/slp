from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from typing import List, Optional
from app.db.base import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    email = Column(String(100), nullable=True, index=True)
    phone = Column(String(20), nullable=True)
    title = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    room_number = Column(String(20), nullable=True)
    preferred_contact_method = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='1')
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    school_assignments = relationship("TeacherSchoolAssignment", back_populates="teacher")
    student_assignments = relationship("StudentTeacherAssignment", back_populates="teacher")
    appointments = relationship("Appointment", back_populates="teacher")
    time_blocks = relationship("TimeBlock", back_populates="teacher")
    teacher_roles = relationship("TeacherRole", back_populates="teacher", cascade="all, delete-orphan")
    
    # New direct student relationships
    students_as_teacher = relationship("Student", foreign_keys="Student.teacher_id", back_populates="teacher")
    students_as_case_manager = relationship("Student", foreign_keys="Student.case_manager_id", back_populates="case_manager")

    @property
    def full_name(self) -> str:
        """Full teacher name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self) -> str:
        """Display name with title if available"""
        if self.title:
            return f"{self.title} {self.full_name}"
        return self.full_name

    @property
    def current_schools(self) -> list:
        """List of schools where teacher is currently assigned"""
        assigned_schools = [
            assignment.school
            for assignment in self.school_assignments
            if assignment.end_date is None and assignment.school and assignment.school.is_active
        ]
        if assigned_schools:
            return assigned_schools

        # Fallback for direct student-school mappings when explicit school assignments are not used.
        schools_by_id = {}
        for student in self.current_students:
            if student.school and student.school.is_active:
                schools_by_id[student.school.id] = student.school
        return list(schools_by_id.values())

    @property
    def primary_school(self):
        """Primary school assignment if any"""
        primary_assignments = [assignment for assignment in self.school_assignments 
                             if assignment.is_primary and assignment.end_date is None]
        return primary_assignments[0].school if primary_assignments else None

    @property
    def current_students(self) -> list:
        """List of students currently assigned to this teacher"""
        students_by_id = {}

        for student in self.students_as_teacher:
            if student and student.enrollment_status == "Active" and not student.is_archived:
                students_by_id[student.id] = student

        for student in self.students_as_case_manager:
            if student and student.enrollment_status == "Active" and not student.is_archived:
                students_by_id[student.id] = student

        # Legacy compatibility path for records still using assignment rows.
        for assignment in self.student_assignments:
            if assignment.end_date is None and assignment.student and assignment.student.enrollment_status == "Active":
                students_by_id[assignment.student.id] = assignment.student

        return list(students_by_id.values())

    @property
    def current_students_count(self) -> int:
        """Count of currently assigned students"""
        return len(self.current_students)

    @property
    def primary_school_name(self) -> Optional[str]:
        """Primary school name if any"""
        primary_school = self.primary_school
        return primary_school.name if primary_school else None

    @property
    def current_schools_names(self) -> List[str]:
        """List of current school names"""
        return [school.name for school in self.current_schools]

    @property
    def active_schools_count(self) -> int:
        """Count of current school assignments"""
        return len(self.current_schools)

    @property
    def roles(self) -> list:
        """List of assigned role entities"""
        return [teacher_role.role for teacher_role in self.teacher_roles if teacher_role.role and teacher_role.role.is_active]
