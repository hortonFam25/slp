from typing import List, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_
from datetime import datetime, date

from app.models.student import Student
from app.models.teacher import Teacher
from app.models.school import School
from app.models.student_teacher_assignment import StudentTeacherAssignment
from app.models.appointment import Appointment
from app.schemas.scheduling_student import (
    StudentScheduleView, 
    StudentScheduleFilters,
    TeacherAssignmentForScheduling,
    SchoolForScheduling,
    AppointmentSummaryForStudent
)


class SchedulingStudentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_students_for_scheduling(
        self, 
        filters: Optional[StudentScheduleFilters] = None
    ) -> List[StudentScheduleView]:
        """
        Get students with all relationships needed for scheduling
        """
        # Start with base query including all relationships
        query = self.db.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager),
            selectinload(Student.teacher_assignments).joinedload(StudentTeacherAssignment.teacher),
        )
        
        # Apply filters
        if filters:
            if filters.school_id:
                query = query.filter(Student.school_id == filters.school_id)
            
            if filters.teacher_id:
                query = query.join(StudentTeacherAssignment).filter(
                    and_(
                        StudentTeacherAssignment.teacher_id == filters.teacher_id,
                        StudentTeacherAssignment.end_date.is_(None)  # Only current assignments
                    )
                )
            
            if filters.grade_level:
                query = query.filter(Student.grade_level == filters.grade_level)
            
            if filters.enrollment_status:
                query = query.filter(Student.enrollment_status == filters.enrollment_status)
        
        students = query.all()
        
        # Convert to scheduling view DTOs
        result = []
        for student in students:
            schedule_view = self._convert_to_schedule_view(student, filters)
            
            # Apply appointment-based filtering if specified
            if filters and filters.has_appointments is not None:
                if filters.has_appointments and not schedule_view.has_appointments:
                    continue
                elif not filters.has_appointments and schedule_view.has_appointments:
                    continue
            
            result.append(schedule_view)
        
        return result

    def _convert_to_schedule_view(
        self, 
        student: Student, 
        filters: Optional[StudentScheduleFilters] = None
    ) -> StudentScheduleView:
        """Convert Student model to StudentScheduleView DTO"""
        
        # Get school info
        school_info = None
        if student.school:
            school_info = SchoolForScheduling(
                id=student.school.id,
                name=student.school.name,
                district_name=getattr(student.school, 'district_name', None)
            )
        
        # Get teacher assignments
        teacher_assignments = []
        primary_teacher = None
        
        for assignment in student.teacher_assignments:
            if assignment.end_date is None:  # Only current assignments
                teacher_assignment = TeacherAssignmentForScheduling(
                    teacher_id=assignment.teacher_id,
                    teacher_name=assignment.teacher.full_name if assignment.teacher else "Unknown Teacher",
                    subject=assignment.subject,
                    is_primary=assignment.is_primary
                )
                teacher_assignments.append(teacher_assignment)
                
                if assignment.is_primary:
                    primary_teacher = teacher_assignment
        
        # Get appointments for the specified date range
        current_appointments = []
        if filters and filters.start_date and filters.end_date:
            start_date = datetime.fromisoformat(filters.start_date).date()
            end_date = datetime.fromisoformat(filters.end_date).date()
            
            appointments = self.db.query(Appointment).filter(
                and_(
                    Appointment.student_id == student.id,
                    Appointment.start_datetime >= start_date,
                    Appointment.start_datetime <= end_date
                )
            ).options(joinedload(Appointment.teacher)).all()
            
            for apt in appointments:
                apt_summary = AppointmentSummaryForStudent(
                    id=apt.id,
                    start_datetime=apt.start_datetime,
                    end_datetime=apt.end_datetime,
                    appointment_type=apt.appointment_type,
                    status=apt.status,
                    teacher_name=apt.teacher.full_name if apt.teacher else None,
                    location=apt.location
                )
                current_appointments.append(apt_summary)
        
        return StudentScheduleView(
            id=student.id,
            student_alias=student.student_alias or f"student_{student.id}",
            first=student.first,
            last=student.last,
            uic=student.uic,
            grade_level=student.grade_level,
            case_manager_name=student.case_manager.display_name if student.case_manager else None,
            enrollment_status=student.enrollment_status,
            school_id=student.school_id,
            school=school_info,
            teacher_assignments=teacher_assignments,
            primary_teacher=primary_teacher,
            current_appointments=current_appointments,
            appointment_count=len(current_appointments),
            has_appointments=len(current_appointments) > 0
        )

    def get_student_for_scheduling(self, student_id: int) -> Optional[StudentScheduleView]:
        """Get a single student with scheduling data"""
        student = self.db.query(Student).options(
            joinedload(Student.school),
            joinedload(Student.teacher),
            joinedload(Student.case_manager),
            selectinload(Student.teacher_assignments).joinedload(StudentTeacherAssignment.teacher),
        ).filter(Student.id == student_id).first()
        
        if not student:
            return None
        
        return self._convert_to_schedule_view(student)
