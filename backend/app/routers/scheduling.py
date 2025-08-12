from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.time_block_repository import TimeBlockRepository
from app.repositories.time_block_activity_repository import TimeBlockActivityRepository
from app.repositories.scheduling_student_repository import SchedulingStudentRepository
from app.services.time_block_scheduling_service import TimeBlockSchedulingService
from app.schemas.appointment import (
    AppointmentCreate, AppointmentRead, AppointmentUpdate, 
    AppointmentSummary, AppointmentWithDetails,
    RecurringAppointmentCreate, RecurringAppointmentResponse
)
from app.schemas.time_block import (
    TimeBlockCreate, TimeBlockRead, TimeBlockUpdate,
    TimeBlockSummary, TimeBlockWithStudents, TimeBlockWithActivities,
    TimeBlockActivityCreate, TimeBlockActivityRead, TimeBlockActivityUpdate,
    TimeBlockScheduleRequest, TimeBlockScheduleResponse
)
from app.schemas.scheduling_student import (
    StudentScheduleView, StudentScheduleFilters
)
from app.schemas.block_assignment import (
    BlockAssignmentCreate, BlockAssignmentRead, BlockAssignmentUpdate,
    BlockAssignmentSummary
)


router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])


# Appointment endpoints
@router.get("/appointments", response_model=List[AppointmentSummary])
def get_appointments(
    start_date: date = Query(..., description="Start date for appointment range"),
    end_date: date = Query(..., description="End date for appointment range"),
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by teacher ID"),
    school_id: Optional[int] = Query(None, description="Filter by school ID"),
    appointment_type: Optional[str] = Query(None, description="Filter by appointment type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get appointments within a date range with optional filters"""
    repo = AppointmentRepository(db)
    appointments = repo.get_appointments_by_date_range(
        start_date=start_date,
        end_date=end_date,
        student_id=student_id,
        teacher_id=teacher_id,
        school_id=school_id,
        appointment_type=appointment_type,
        status=status
    )
    
    # Convert to summary format
    summaries = []
    for apt in appointments:
        summary = AppointmentSummary(
            id=apt.id,
            student_id=apt.student_id,
            student_name=apt.student.full_name if apt.student else "Unknown",
            teacher_id=apt.teacher_id,
            teacher_name=apt.teacher.full_name if apt.teacher else None,
            school_id=apt.school_id,
            school_name=apt.school.name if apt.school else None,
            start_datetime=apt.start_datetime,
            end_datetime=apt.end_datetime,
            appointment_type=apt.appointment_type,
            status=apt.status,
            location=apt.location,
            duration_minutes=apt.duration_minutes
        )
        summaries.append(summary)
    
    return summaries


@router.get("/appointments/{appointment_id}", response_model=AppointmentWithDetails)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Get a specific appointment with details"""
    repo = AppointmentRepository(db)
    appointment = repo.get_appointment(appointment_id)
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return AppointmentWithDetails(
        **appointment.__dict__,
        student_name=appointment.student.full_name if appointment.student else "Unknown",
        teacher_name=appointment.teacher.full_name if appointment.teacher else None,
        school_name=appointment.school.name if appointment.school else None,
        duration_minutes=appointment.duration_minutes,
        can_start_session=appointment.can_start_session
    )


@router.post("/appointments", response_model=AppointmentRead)
def create_appointment(appointment_data: AppointmentCreate, db: Session = Depends(get_db)):
    """Create a new appointment"""
    repo = AppointmentRepository(db)
    
    # Check for time conflicts
    if repo.check_time_conflict(
        student_id=appointment_data.student_id,
        start_datetime=appointment_data.start_datetime,
        end_datetime=appointment_data.end_datetime
    ):
        raise HTTPException(
            status_code=400, 
            detail="Student has a conflicting appointment in this time slot"
        )
    
    appointment = repo.create_appointment(appointment_data)
    return appointment


@router.post("/appointments/recurring", response_model=RecurringAppointmentResponse)
def create_recurring_appointments(recurring_data: RecurringAppointmentCreate, db: Session = Depends(get_db)):
    """Create recurring appointments with therapy sessions, goals, and objectives"""
    repo = AppointmentRepository(db)
    
    result = repo.create_recurring_appointments(recurring_data)
    
    return RecurringAppointmentResponse(
        appointments=result['appointments'],
        total_created=result['total_created'],
        conflicts=result['conflicts'],
        series_id=result['series_id']
    )


@router.put("/appointments/{appointment_id}", response_model=AppointmentRead)
def update_appointment(
    appointment_id: int, 
    appointment_data: AppointmentUpdate, 
    db: Session = Depends(get_db)
):
    """Update an appointment"""
    repo = AppointmentRepository(db)
    
    # If updating time, check for conflicts
    if appointment_data.start_datetime or appointment_data.end_datetime:
        existing = repo.get_appointment(appointment_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        start_time = appointment_data.start_datetime or existing.start_datetime
        end_time = appointment_data.end_datetime or existing.end_datetime
        student_id = appointment_data.student_id or existing.student_id
        
        if repo.check_time_conflict(
            student_id=student_id,
            start_datetime=start_time,
            end_datetime=end_time,
            exclude_appointment_id=appointment_id
        ):
            raise HTTPException(
                status_code=400, 
                detail="Student has a conflicting appointment in this time slot"
            )
    
    appointment = repo.update_appointment(appointment_id, appointment_data)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return appointment


@router.delete("/appointments/{appointment_id}")
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Delete an appointment"""
    repo = AppointmentRepository(db)
    success = repo.delete_appointment(appointment_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return {"message": "Appointment deleted successfully"}


@router.get("/appointments/series/{series_id}")
def get_appointments_by_series(series_id: str, db: Session = Depends(get_db)):
    """Get all appointments in a series"""
    repo = AppointmentRepository(db)
    appointments = repo.get_appointments_by_series(series_id)
    
    if not appointments:
        raise HTTPException(status_code=404, detail="Series not found")
    
    return appointments


@router.delete("/appointments/series/{series_id}")
def delete_appointment_series(series_id: str, db: Session = Depends(get_db)):
    """Delete an entire appointment series"""
    repo = AppointmentRepository(db)
    success = repo.delete_appointment_series(series_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Series not found")
    
    return {"message": "Appointment series deleted successfully"}


@router.put("/appointments/series/{series_id}")
def update_appointment_series(
    series_id: str, 
    appointment_data: AppointmentUpdate, 
    db: Session = Depends(get_db)
):
    """Update all appointments in a series"""
    repo = AppointmentRepository(db)
    
    # Get series first to validate it exists
    appointments = repo.get_appointments_by_series(series_id)
    if not appointments:
        raise HTTPException(status_code=404, detail="Series not found")
    
    # Update all appointments in the series
    updated_appointments = repo.update_appointment_series(series_id, appointment_data)
    
    return {
        "message": "Appointment series updated successfully",
        "updated_count": len(updated_appointments),
        "appointments": updated_appointments
    }


@router.get("/students/{student_id}/appointments", response_model=List[AppointmentSummary])
def get_student_appointments(
    student_id: int,
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    db: Session = Depends(get_db)
):
    """Get all appointments for a specific student"""
    repo = AppointmentRepository(db)
    appointments = repo.get_student_appointments(student_id, start_date, end_date)
    
    summaries = []
    for apt in appointments:
        summary = AppointmentSummary(
            id=apt.id,
            student_id=apt.student_id,
            student_name=apt.student.full_name if apt.student else "Unknown",
            teacher_id=apt.teacher_id,
            teacher_name=apt.teacher.full_name if apt.teacher else None,
            school_id=apt.school_id,
            school_name=apt.school.name if apt.school else None,
            start_datetime=apt.start_datetime,
            end_datetime=apt.end_datetime,
            appointment_type=apt.appointment_type,
            status=apt.status,
            location=apt.location,
            duration_minutes=apt.duration_minutes
        )
        summaries.append(summary)
    
    return summaries


@router.get("/students/{student_id}/available-slots")
def get_available_slots(
    student_id: int,
    target_date: date = Query(..., description="Date to check for available slots"),
    duration_minutes: int = Query(30, description="Duration of appointment in minutes"),
    start_hour: int = Query(8, description="Start hour for time slots"),
    end_hour: int = Query(17, description="End hour for time slots"),
    db: Session = Depends(get_db)
):
    """Get available time slots for a student on a given date"""
    repo = AppointmentRepository(db)
    slots = repo.get_available_time_slots(
        student_id=student_id,
        target_date=target_date,
        duration_minutes=duration_minutes,
        start_hour=start_hour,
        end_hour=end_hour
    )
    
    return {"available_slots": slots}


# Time Block endpoints
@router.get("/time-blocks", response_model=List[TimeBlockSummary])
def get_time_blocks(
    start_date: date = Query(..., description="Start date for time block range"),
    end_date: date = Query(..., description="End date for time block range"),
    teacher_id: Optional[int] = Query(None, description="Filter by teacher ID"),
    school_id: Optional[int] = Query(None, description="Filter by school ID"),
    block_type: Optional[str] = Query(None, description="Filter by block type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    available_only: bool = Query(False, description="Show only blocks with available spots"),
    db: Session = Depends(get_db)
):
    """Get time blocks within a date range with optional filters"""
    repo = TimeBlockRepository(db)
    
    if available_only:
        time_blocks = repo.get_available_time_blocks(
            start_date=start_date,
            end_date=end_date,
            school_id=school_id,
            block_type=block_type
        )
    else:
        time_blocks = repo.get_time_blocks_by_date_range(
            start_date=start_date,
            end_date=end_date,
            teacher_id=teacher_id,
            school_id=school_id,
            block_type=block_type,
            status=status
        )
    
    # Convert to summary format
    summaries = []
    for block in time_blocks:
        summary = TimeBlockSummary(
            id=block.id,
            teacher_id=block.teacher_id,
            teacher_name=block.teacher.full_name if block.teacher else None,
            school_id=block.school_id,
            school_name=block.school.name if block.school else None,
            start_datetime=block.start_datetime,
            end_datetime=block.end_datetime,
            block_type=block.block_type,
            title=block.title,
            max_students=block.max_students,
            location=block.location,
            status=block.status,
            current_student_count=block.current_student_count,
            available_spots=block.available_spots,
            duration_minutes=block.duration_minutes
        )
        summaries.append(summary)
    
    return summaries


@router.get("/time-blocks/{time_block_id}", response_model=TimeBlockWithStudents)
def get_time_block(time_block_id: int, db: Session = Depends(get_db)):
    """Get a specific time block with student details"""
    repo = TimeBlockRepository(db)
    time_block = repo.get_time_block(time_block_id)
    
    if not time_block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    from app.schemas.student import StudentSummary
    assigned_students = [
        StudentSummary(
            id=assignment.student.id,
            first=assignment.student.first,
            last=assignment.student.last,
            uic=assignment.student.uic,
            grade_level=assignment.student.grade_level,
            enrollment_status=assignment.student.enrollment_status,
            case_manager=assignment.student.case_manager
        )
        for assignment in time_block.block_assignments
        if assignment.status == 'assigned'
    ]
    
    return TimeBlockWithStudents(
        **time_block.__dict__,
        teacher_name=time_block.teacher.full_name if time_block.teacher else None,
        school_name=time_block.school.name if time_block.school else None,
        duration_minutes=time_block.duration_minutes,
        current_student_count=time_block.current_student_count,
        available_spots=time_block.available_spots,
        is_full=time_block.is_full,
        assigned_students=assigned_students
    )


@router.post("/time-blocks", response_model=TimeBlockRead)
def create_time_block(time_block_data: TimeBlockCreate, db: Session = Depends(get_db)):
    """Create a new time block"""
    repo = TimeBlockRepository(db)
    
    # Check for teacher conflicts if teacher_id is provided
    if time_block_data.teacher_id:
        if repo.check_teacher_conflict(
            teacher_id=time_block_data.teacher_id,
            start_datetime=time_block_data.start_datetime,
            end_datetime=time_block_data.end_datetime
        ):
            raise HTTPException(
                status_code=400, 
                detail="Teacher has a conflicting time block in this time slot"
            )
    
    time_block = repo.create_time_block(time_block_data)
    return time_block


@router.put("/time-blocks/{time_block_id}", response_model=TimeBlockRead)
def update_time_block(
    time_block_id: int, 
    time_block_data: TimeBlockUpdate, 
    db: Session = Depends(get_db)
):
    """Update a time block"""
    repo = TimeBlockRepository(db)
    
    # If updating time or teacher, check for conflicts
    if (time_block_data.start_datetime or time_block_data.end_datetime or 
        time_block_data.teacher_id):
        existing = repo.get_time_block(time_block_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Time block not found")
        
        start_time = time_block_data.start_datetime or existing.start_datetime
        end_time = time_block_data.end_datetime or existing.end_datetime
        teacher_id = time_block_data.teacher_id or existing.teacher_id
        
        if teacher_id and repo.check_teacher_conflict(
            teacher_id=teacher_id,
            start_datetime=start_time,
            end_datetime=end_time,
            exclude_block_id=time_block_id
        ):
            raise HTTPException(
                status_code=400, 
                detail="Teacher has a conflicting time block in this time slot"
            )
    
    time_block = repo.update_time_block(time_block_id, time_block_data)
    if not time_block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    return time_block


@router.delete("/time-blocks/{time_block_id}")
def delete_time_block(time_block_id: int, db: Session = Depends(get_db)):
    """Delete a time block"""
    repo = TimeBlockRepository(db)
    success = repo.delete_time_block(time_block_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    return {"message": "Time block deleted successfully"}


@router.post("/time-blocks/{time_block_id}/students/{student_id}")
def assign_student_to_block(
    time_block_id: int, 
    student_id: int, 
    db: Session = Depends(get_db)
):
    """Assign a student to a time block"""
    repo = TimeBlockRepository(db)
    success = repo.assign_student_to_block(time_block_id, student_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Unable to assign student to time block (block may be full or student already assigned)"
        )
    
    return {"message": "Student assigned to time block successfully"}


@router.delete("/time-blocks/{time_block_id}/students/{student_id}")
def remove_student_from_block(
    time_block_id: int, 
    student_id: int, 
    db: Session = Depends(get_db)
):
    """Remove a student from a time block"""
    repo = TimeBlockRepository(db)
    success = repo.remove_student_from_block(time_block_id, student_id)
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Student assignment not found"
        )
    
    return {"message": "Student removed from time block successfully"}


# =====================================
# Students for Scheduling
# =====================================

@router.get("/students", response_model=List[StudentScheduleView])
def get_students_for_scheduling(
    school_id: Optional[int] = Query(None, description="Filter by school ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by teacher ID"),
    grade_level: Optional[str] = Query(None, description="Filter by grade level"),
    enrollment_status: Optional[str] = Query(None, description="Filter by enrollment status"),
    start_date: Optional[str] = Query(None, description="Start date for appointment filtering (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for appointment filtering (YYYY-MM-DD)"),
    has_appointments: Optional[bool] = Query(None, description="Filter by appointment status (true=scheduled, false=unscheduled)"),
    db: Session = Depends(get_db)
):
    """Get students with comprehensive data for scheduling functionality"""
    filters = StudentScheduleFilters(
        school_id=school_id,
        teacher_id=teacher_id,
        grade_level=grade_level,
        enrollment_status=enrollment_status,
        start_date=start_date,
        end_date=end_date,
        has_appointments=has_appointments
    )
    
    repo = SchedulingStudentRepository(db)
    return repo.get_students_for_scheduling(filters)


@router.get("/students/{student_id}", response_model=StudentScheduleView)
def get_student_for_scheduling(
    student_id: int,
    db: Session = Depends(get_db)
):
    """Get a single student with comprehensive scheduling data"""
    repo = SchedulingStudentRepository(db)
    student = repo.get_student_for_scheduling(student_id)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return student


# =====================================
# Time Block Activities
# =====================================

@router.get("/time-blocks/{time_block_id}/activities", response_model=List[TimeBlockActivityRead])
def get_time_block_activities(time_block_id: int, db: Session = Depends(get_db)):
    """Get all activities for a time block"""
    repo = TimeBlockActivityRepository(db)
    return repo.get_activities_by_time_block(time_block_id)


@router.post("/time-blocks/{time_block_id}/activities", response_model=TimeBlockActivityRead)
def create_time_block_activity(
    time_block_id: int,
    activity_data: TimeBlockActivityCreate,
    db: Session = Depends(get_db)
):
    """Create a new activity for a time block"""
    # Ensure the time_block_id matches
    activity_data.time_block_id = time_block_id
    
    repo = TimeBlockActivityRepository(db)
    
    # Check for time overlap
    if repo.check_time_overlap(
        time_block_id=time_block_id,
        start_minute=activity_data.start_minute,
        duration_minutes=activity_data.duration_minutes
    ):
        raise HTTPException(
            status_code=400,
            detail="Activity time overlaps with existing activity"
        )
    
    # Set sequence order if not provided
    if not hasattr(activity_data, 'sequence_order') or not activity_data.sequence_order:
        activity_data.sequence_order = repo.get_next_sequence_order(time_block_id)
    
    return repo.create_activity(activity_data)


@router.put("/time-blocks/{time_block_id}/activities/{activity_id}", response_model=TimeBlockActivityRead)
def update_time_block_activity(
    time_block_id: int,
    activity_id: int,
    activity_data: TimeBlockActivityUpdate,
    db: Session = Depends(get_db)
):
    """Update a time block activity"""
    repo = TimeBlockActivityRepository(db)
    
    # Check if activity exists and belongs to the time block
    existing_activity = repo.get_activity(activity_id)
    if not existing_activity or existing_activity.time_block_id != time_block_id:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Check for time overlap if time is being changed
    if activity_data.start_minute is not None or activity_data.duration_minutes is not None:
        start_minute = activity_data.start_minute or existing_activity.start_minute
        duration_minutes = activity_data.duration_minutes or existing_activity.duration_minutes
        
        if repo.check_time_overlap(
            time_block_id=time_block_id,
            start_minute=start_minute,
            duration_minutes=duration_minutes,
            exclude_activity_id=activity_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Activity time overlaps with existing activity"
            )
    
    activity = repo.update_activity(activity_id, activity_data)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return activity


@router.delete("/time-blocks/{time_block_id}/activities/{activity_id}")
def delete_time_block_activity(
    time_block_id: int,
    activity_id: int,
    db: Session = Depends(get_db)
):
    """Delete a time block activity"""
    repo = TimeBlockActivityRepository(db)
    
    # Check if activity exists and belongs to the time block
    existing_activity = repo.get_activity(activity_id)
    if not existing_activity or existing_activity.time_block_id != time_block_id:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    success = repo.delete_activity(activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return {"message": "Activity deleted successfully"}


@router.put("/time-blocks/{time_block_id}/activities/reorder")
def reorder_time_block_activities(
    time_block_id: int,
    activity_order: List[int],
    db: Session = Depends(get_db)
):
    """Reorder activities in a time block"""
    repo = TimeBlockActivityRepository(db)
    activities = repo.reorder_activities(time_block_id, activity_order)
    return {"message": "Activities reordered successfully", "activities": activities}


@router.get("/time-blocks/{time_block_id}/available-slots")
def get_available_activity_slots(
    time_block_id: int,
    duration_minutes: int = Query(5, description="Duration of new activity in minutes"),
    db: Session = Depends(get_db)
):
    """Get available time slots for new activities"""
    repo = TimeBlockActivityRepository(db)
    return repo.get_available_time_slots(time_block_id, duration_minutes)


# =====================================
# Time Block Scheduling
# =====================================

@router.post("/time-blocks/schedule", response_model=TimeBlockScheduleResponse)
def schedule_time_block(
    schedule_request: TimeBlockScheduleRequest,
    db: Session = Depends(get_db)
):
    """Schedule a time block by creating appointments for assigned students"""
    service = TimeBlockSchedulingService(db)
    
    try:
        result = service.schedule_time_block(
            time_block_id=schedule_request.time_block_id,
            recurring_config=schedule_request.recurring_config,
            student_goal_assignments=schedule_request.student_goal_assignments
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule time block: {str(e)}")


@router.delete("/time-blocks/{time_block_id}/schedule")
def cancel_time_block_schedule(
    time_block_id: int,
    cancel_future_only: bool = Query(True, description="Cancel only future appointments"),
    db: Session = Depends(get_db)
):
    """Cancel scheduled appointments for a time block"""
    service = TimeBlockSchedulingService(db)
    
    try:
        result = service.cancel_time_block_schedule(time_block_id, cancel_future_only)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel time block schedule: {str(e)}")


@router.get("/time-blocks/{time_block_id}/appointments")
def get_time_block_appointments(
    time_block_id: int,
    db: Session = Depends(get_db)
):
    """Get all appointments for a time block"""
    service = TimeBlockSchedulingService(db)
    appointments = service.get_time_block_appointments(time_block_id)
    
    return [
        {
            "id": apt.id,
            "student_id": apt.student_id,
            "student_name": f"{apt.student.first} {apt.student.last}",
            "start_datetime": apt.start_datetime,
            "end_datetime": apt.end_datetime,
            "status": apt.status,
            "has_therapy_session": apt.has_therapy_session,
            "session_status": apt.session_status
        }
        for apt in appointments
    ]


# Enhanced time block detail with activities
@router.get("/time-blocks/{time_block_id}/detailed", response_model=TimeBlockWithActivities)
def get_time_block_with_activities(time_block_id: int, db: Session = Depends(get_db)):
    """Get a time block with students and activities"""
    from app.schemas.student import StudentSummary
    
    # Get time block
    time_block_repo = TimeBlockRepository(db)
    time_block = time_block_repo.get_time_block(time_block_id)
    
    if not time_block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    # Get activities
    activity_repo = TimeBlockActivityRepository(db)
    activities = activity_repo.get_activities_by_time_block(time_block_id)
    
    # Get assigned students
    assigned_students = [
        StudentSummary(
            id=assignment.student.id,
            first=assignment.student.first,
            last=assignment.student.last,
            uic=assignment.student.uic,
            grade_level=assignment.student.grade_level,
            enrollment_status=assignment.student.enrollment_status,
            case_manager=assignment.student.case_manager
        )
        for assignment in time_block.block_assignments
        if assignment.status == 'assigned'
    ]
    
    return TimeBlockWithActivities(
        **time_block.__dict__,
        teacher_name=time_block.teacher.full_name if time_block.teacher else None,
        school_name=time_block.school.name if time_block.school else None,
        duration_minutes=time_block.duration_minutes,
        current_student_count=time_block.current_student_count,
        available_spots=time_block.available_spots,
        is_full=time_block.is_full,
        assigned_students=assigned_students,
        activities=activities
    )
