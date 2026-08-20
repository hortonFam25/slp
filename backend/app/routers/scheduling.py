import logging
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.database import get_db
from app.dependencies.access_control import ensure_appointment_access
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.time_block_repository import TimeBlockRepository
from app.repositories.time_block_activity_repository import TimeBlockActivityRepository
from app.repositories.scheduling_student_repository import SchedulingStudentRepository
from app.services.time_block_scheduling_service import TimeBlockSchedulingService
from app.schemas.appointment import (
    AppointmentCreate, AppointmentRead, AppointmentUpdate, 
    AppointmentSummary, AppointmentWithDetails,
    RecurringAppointmentCreate, RecurringAppointmentResponse,
    SeriesPatternUpdate
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
from app.schemas.student import StudentSummary
from app.schemas.block_assignment import (
    BlockAssignmentCreate, BlockAssignmentRead, BlockAssignmentUpdate,
    BlockAssignmentSummary
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"], dependencies=[Depends(get_auth_context)])


def _should_mask_student_names(auth: AuthContext) -> bool:
    return auth.is_admin or auth.user.id != auth.effective_user.id


def _student_alias_value(student) -> str:
    return getattr(student, "student_alias", None) or f"student_{student.id}"


def _student_display_name(student, auth: AuthContext) -> str:
    if student is None:
        return "Unknown"
    if _should_mask_student_names(auth):
        return _student_alias_value(student)
    return student.full_name


def _student_name_parts(student, auth: AuthContext) -> tuple[str, str]:
    if _should_mask_student_names(auth):
        return _student_alias_value(student), ""
    return student.first, student.last


def _student_summary_for_response(student, auth: AuthContext) -> StudentSummary:
    first, last = _student_name_parts(student, auth)
    return StudentSummary(
        id=student.id,
        student_alias=student.student_alias or f"student_{student.id}",
        first=first,
        last=last,
        uic=student.uic,
        grade_level=student.grade_level,
        enrollment_status=student.enrollment_status,
        school_id=student.school_id,
        teacher_id=student.teacher_id,
        case_manager_id=student.case_manager_id,
        teacher=student.teacher,
        case_manager=student.case_manager,
    )


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
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get appointments within a date range with optional filters"""
    if student_id is not None:
        ensure_student_access(auth, student_id, action="list appointments for student")
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
    
    if auth.enforce_access and not auth.is_admin:
        appointments = [a for a in appointments if a.student_id in auth.allowed_student_ids]

    # Convert to summary format
    summaries = []
    for apt in appointments:
        summary = AppointmentSummary(
            id=apt.id,
            student_id=apt.student_id,
            student_name=_student_display_name(apt.student, auth),
            teacher_id=apt.teacher_id,
            teacher_name=apt.teacher.full_name if apt.teacher else None,
            school_id=apt.school_id,
            school_name=apt.school.name if apt.school else None,
            start_datetime=apt.start_datetime,
            end_datetime=apt.end_datetime,
            appointment_type=apt.appointment_type,
            status=apt.status,
            location=apt.location,
            duration_minutes=apt.duration_minutes,
            series_id=apt.series_id,
            notes=apt.notes,
            therapy_session_status=apt.therapy_session.status if apt.therapy_session else None
        )
        summaries.append(summary)
    
    return summaries


@router.get("/appointments/{appointment_id}", response_model=AppointmentWithDetails)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific appointment with details"""
    repo = AppointmentRepository(db)
    appointment = repo.get_appointment(appointment_id)
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    ensure_appointment_access(db, auth, appointment_id)
    
    return AppointmentWithDetails(
        **appointment.__dict__,
        student_name=_student_display_name(appointment.student, auth),
        teacher_name=appointment.teacher.full_name if appointment.teacher else None,
        school_name=appointment.school.name if appointment.school else None,
        duration_minutes=appointment.duration_minutes,
        can_start_session=appointment.can_start_session
    )


@router.post("/appointments", response_model=AppointmentRead)
def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create a new appointment"""
    ensure_student_access(auth, appointment_data.student_id, action="create appointment")
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
def create_recurring_appointments(
    recurring_data: RecurringAppointmentCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Create recurring appointments with therapy sessions, goals, and objectives"""
    ensure_student_access(auth, recurring_data.student_id, action="create recurring appointments")
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
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Update an appointment"""
    repo = AppointmentRepository(db)
    ensure_appointment_access(db, auth, appointment_id)
    
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
    
    try:
        appointment = repo.update_appointment(appointment_id, appointment_data)
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/appointments/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Delete an appointment"""
    repo = AppointmentRepository(db)
    ensure_appointment_access(db, auth, appointment_id)
    
    try:
        success = repo.delete_appointment(appointment_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        return {"message": "Appointment deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.put("/appointments/series/{series_id}/pattern")
def update_appointment_series_pattern(
    series_id: str, 
    pattern_data: SeriesPatternUpdate, 
    db: Session = Depends(get_db)
):
    """Update appointment series with pattern-aware logic"""
    logger.info("Appointment series pattern update for series %s", series_id)
    logger.debug("Received pattern_data: %s", pattern_data)
    
    repo = AppointmentRepository(db)
    
    # Get series first to validate it exists
    appointments = repo.get_appointments_by_series(series_id)
    if not appointments:
        raise HTTPException(status_code=404, detail="Series not found")
    
    try:
        # Update appointments using pattern logic
        updated_appointments = repo.update_appointment_series_pattern(series_id, pattern_data)
        
        # Update corresponding time blocks to match the updated appointments
        time_block_repo = TimeBlockRepository(db)
        time_block_ids = list(set([apt.time_block_id for apt in updated_appointments if apt.time_block_id]))
        updated_time_blocks = []
        
        logger.debug("Updating %d time blocks to match appointment changes", len(time_block_ids))
        
        for time_block_id in time_block_ids:
            time_block = time_block_repo.get_time_block(time_block_id)
            if time_block:
                # Find appointments for this time block to get the new times
                block_appointments = [apt for apt in updated_appointments if apt.time_block_id == time_block_id]
                if block_appointments:
                    # Get the earliest start and latest end from all appointments in this time block
                    start_times = [apt.start_datetime for apt in block_appointments]
                    end_times = [apt.end_datetime for apt in block_appointments]
                    
                    old_start = time_block.start_datetime
                    old_end = time_block.end_datetime
                    
                    time_block.start_datetime = min(start_times)
                    time_block.end_datetime = max(end_times)
                    time_block.modified_date = datetime.now()
                    
                    logger.debug(
                        "Updating time block %s: %s to %s",
                        time_block_id,
                        old_start,
                        time_block.start_datetime,
                    )
                    
                    updated_time_blocks.append(time_block)
        
        db.commit()
        
        return {
            "message": f"Series pattern updated successfully - {len(updated_appointments)} appointments and {len(updated_time_blocks)} time blocks",
            "updated_count": len(updated_appointments),
            "updated_time_blocks": len(updated_time_blocks),
            "appointments": updated_appointments,
            "time_blocks": updated_time_blocks
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/students/{student_id}/appointments", response_model=List[AppointmentSummary])
def get_student_appointments(
    student_id: int,
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all appointments for a specific student"""
    ensure_student_access(auth, student_id, action="get student appointments")
    repo = AppointmentRepository(db)
    appointments = repo.get_student_appointments(student_id, start_date, end_date)
    
    summaries = []
    for apt in appointments:
        summary = AppointmentSummary(
            id=apt.id,
            student_id=apt.student_id,
            student_name=_student_display_name(apt.student, auth),
            teacher_id=apt.teacher_id,
            teacher_name=apt.teacher.full_name if apt.teacher else None,
            school_id=apt.school_id,
            school_name=apt.school.name if apt.school else None,
            start_datetime=apt.start_datetime,
            end_datetime=apt.end_datetime,
            appointment_type=apt.appointment_type,
            status=apt.status,
            location=apt.location,
            duration_minutes=apt.duration_minutes,
            series_id=apt.series_id,
            notes=apt.notes,
            therapy_session_status=apt.therapy_session.status if apt.therapy_session else None
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
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get available time slots for a student on a given date"""
    ensure_student_access(auth, student_id, action="get available slots")
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
def get_time_block(
    time_block_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a specific time block with student details"""
    repo = TimeBlockRepository(db)
    time_block = repo.get_time_block(time_block_id)
    
    if not time_block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    assigned_students = [
        _student_summary_for_response(assignment.student, auth)
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


@router.post("/time-blocks/recurring")
def create_recurring_time_blocks(request_data: dict, db: Session = Depends(get_db)):
    """Create recurring time blocks with appointments for all assigned students"""
    repo = TimeBlockRepository(db)
    
    # Extract data from request
    time_block_data = request_data.get('time_block_data', {})
    student_ids = request_data.get('student_ids', [])
    recurring_config = request_data.get('recurring_config', {})
    activities_data = request_data.get('activities_data', [])
    
    # Validate required fields
    if not time_block_data:
        raise HTTPException(status_code=400, detail="time_block_data is required")
    if not student_ids:
        raise HTTPException(status_code=400, detail="student_ids is required")
    if not recurring_config:
        raise HTTPException(status_code=400, detail="recurring_config is required")
    
    try:
        result = repo.create_recurring_time_blocks(
            time_block_data=time_block_data,
            student_ids=student_ids,
            recurring_config=recurring_config,
            activities_data=activities_data
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.put("/time-blocks/series/{series_id}")
def update_time_block_series(
    series_id: str,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """Update all time blocks in a series (for recurring time blocks)"""
    time_block_repo = TimeBlockRepository(db)
    
    try:
        result = time_block_repo.update_time_block_series(series_id, update_data)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "Series not found"))
        
        return {
            "message": result["message"],
            "updated_time_blocks": result["updated_time_blocks"],
            "updated_appointments": result["updated_appointments"],
            "recalculated_time_slots": result["recalculated_time_slots"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update time block series: {str(e)}")


@router.put("/time-blocks/series/{series_id}/pattern")
def update_time_block_series_pattern(
    series_id: str,
    pattern_data: dict,
    db: Session = Depends(get_db)
):
    """Update time block series with pattern changes (date shifts, day alignment)"""
    from app.repositories.appointment_repository import AppointmentRepository
    from app.schemas.appointment import SeriesPatternUpdate
    
    logger.info("Using appointment pattern logic for time block series %s", series_id)
    logger.debug("Pattern data: %s", pattern_data)
    
    try:
        appointment_repo = AppointmentRepository(db)
        time_block_repo = TimeBlockRepository(db)
        
        # Convert to SeriesPatternUpdate schema (same as EditAppointmentModal)
        series_pattern_update = SeriesPatternUpdate(
            update_type=pattern_data.get('update_type', 'day_alignment'),
            start_datetime=datetime.fromisoformat(pattern_data['start_datetime']) if pattern_data.get('start_datetime') else None,
            end_datetime=datetime.fromisoformat(pattern_data['end_datetime']) if pattern_data.get('end_datetime') else None,
            date_offset_days=pattern_data.get('date_offset_days', 0),
            target_day_of_week=pattern_data.get('target_day_of_week'),
            notes=pattern_data.get('notes')
        )
        
        # Use the existing appointment series pattern update (this works for individual appointments)
        updated_appointments = appointment_repo.update_appointment_series_pattern(series_id, series_pattern_update)
        
        logger.info(
            "Appointment pattern update completed - %d appointments updated",
            len(updated_appointments),
        )
        
        # Now update the time blocks to match the updated appointments
        time_block_ids = list(set([apt.time_block_id for apt in updated_appointments if apt.time_block_id]))
        updated_time_blocks = []
        
        for time_block_id in time_block_ids:
            time_block = time_block_repo.get_time_block(time_block_id)
            if time_block:
                # Find appointments for this time block to get the new times
                block_appointments = [apt for apt in updated_appointments if apt.time_block_id == time_block_id]
                if block_appointments:
                    # Get the earliest start and latest end from all appointments in this time block
                    start_times = [apt.start_datetime for apt in block_appointments]
                    end_times = [apt.end_datetime for apt in block_appointments]
                    
                    old_start = time_block.start_datetime
                    old_end = time_block.end_datetime
                    
                    time_block.start_datetime = min(start_times)
                    time_block.end_datetime = max(end_times)
                    time_block.modified_date = datetime.now()
                    
                    logger.debug(
                        "Updating time block %s: %s to %s",
                        time_block_id,
                        old_start,
                        time_block.start_datetime,
                    )
                    
                    # Update other fields if provided
                    if pattern_data.get('title'):
                        time_block.title = pattern_data['title']
                    if pattern_data.get('location'):
                        time_block.location = pattern_data['location']
                    if pattern_data.get('notes'):
                        time_block.notes = pattern_data['notes']
                    
                    updated_time_blocks.append(time_block)
        
        db.commit()
        
        logger.info(
            "Updated %d time blocks and %d appointments",
            len(updated_time_blocks),
            len(updated_appointments),
        )
        
        return {
            "message": "Time block series pattern updated successfully",
            "updated_time_blocks": len(updated_time_blocks),
            "updated_appointments": len(updated_appointments),
            "time_blocks": updated_time_blocks,
            "appointments": updated_appointments
        }
    except Exception as e:
        logger.exception("Time block pattern update failed for series %s", series_id)
        raise HTTPException(status_code=500, detail=f"Failed to update time block series pattern: {str(e)}")


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
    auto_create_appointments: bool = Query(True, description="Automatically create appointments with time splitting"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Assign a student to a time block with optional automatic appointment creation"""
    ensure_student_access(auth, student_id, action="assign student to time block")
    repo = TimeBlockRepository(db)
    
    if auto_create_appointments:
        result = repo.assign_student_with_auto_scheduling(time_block_id, student_id, auto_create_appointments=True)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    else:
        success = repo.assign_student_to_block(time_block_id, student_id)
        if not success:
            raise HTTPException(
                status_code=400, 
                detail="Unable to assign student to time block (block may be full or student already assigned)"
            )
        return {"message": "Student assigned to time block successfully"}


@router.get("/time-blocks/{time_block_id}/eligible-students")
def get_eligible_students_for_time_block(
    time_block_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get students eligible for assignment to this time block based on teacher/case manager"""
    repo = TimeBlockRepository(db)
    students = repo.get_eligible_students_for_time_block(time_block_id)
    
    return [
        _student_summary_for_response(student, auth)
        for student in students
    ]


@router.get("/students/by-teacher/{teacher_id}")
def get_students_by_teacher_or_case_manager(
    teacher_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get students who have this person as either teacher or case manager"""
    from app.models.student import Student
    from sqlalchemy.orm import joinedload
    
    students = db.query(Student).options(
        joinedload(Student.teacher),
        joinedload(Student.case_manager),
        joinedload(Student.school)
    ).filter(
        and_(
            or_(
                Student.teacher_id == teacher_id,
                Student.case_manager_id == teacher_id
            ),
            Student.enrollment_status == 'Active',
            Student.is_archived == False
        )
    ).order_by(Student.last, Student.first).all()
    
    return [
        _student_summary_for_response(student, auth)
        for student in students
    ]


@router.delete("/time-blocks/{time_block_id}/students/{student_id}")
def remove_student_from_block(
    time_block_id: int, 
    student_id: int,
    auto_update_appointments: bool = Query(True, description="Automatically recalculate remaining appointments"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove a student from a time block with optional automatic appointment rescheduling"""
    ensure_student_access(auth, student_id, action="remove student from time block")
    repo = TimeBlockRepository(db)
    
    if auto_update_appointments:
        result = repo.remove_student_with_auto_rescheduling(time_block_id, student_id, auto_update_appointments=True)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    else:
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
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
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
    students = repo.get_students_for_scheduling(filters)
    if _should_mask_student_names(auth):
        for student in students:
            student.first = student.student_alias
            student.last = ""
    return students


@router.get("/students/{student_id}", response_model=StudentScheduleView)
def get_student_for_scheduling(
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a single student with comprehensive scheduling data"""
    ensure_student_access(auth, student_id, action="get student scheduling view")
    repo = SchedulingStudentRepository(db)
    student = repo.get_student_for_scheduling(student_id)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if _should_mask_student_names(auth):
        student.first = student.student_alias
        student.last = ""
    return student


# =====================================
# Time Block Activities
# =====================================

@router.get("/time-blocks/{time_block_id}/activities")
def get_time_block_activities(
    time_block_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all activities for a time block"""
    repo = TimeBlockActivityRepository(db)
    raw_activities = repo.get_activities_by_time_block(time_block_id)
    
    # Manually serialize activities to avoid Student object validation errors
    activities = []
    for activity in raw_activities:
        assigned_students = []
        if hasattr(activity, 'student_assignments'):
            for assignment in activity.student_assignments:
                if assignment.status == 'assigned' and assignment.student:
                    first, last = _student_name_parts(assignment.student, auth)
                    assigned_students.append({
                        "id": assignment.student.id,
                        "first": first,
                        "last": last,
                        "full_name": _student_display_name(assignment.student, auth)
                    })
        
        activity_dict = {
            "id": activity.id,
            "time_block_id": activity.time_block_id,
            "start_minute": activity.start_minute,
            "duration_minutes": activity.duration_minutes,
            "start_datetime": activity.start_datetime,
            "end_datetime": activity.end_datetime,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "materials_needed": activity.materials_needed,
            "notes": activity.notes,
            "sequence_order": activity.sequence_order,
            "assigned_student_ids": [s["id"] for s in assigned_students],
            "created_date": activity.created_date,
            "modified_date": activity.modified_date,
            "created_by": activity.created_by,
            "assigned_students": assigned_students
        }
        activities.append(activity_dict)
    
    return activities


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
    
    try:
        return repo.create_activity(activity_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/time-blocks/{time_block_id}/activities/{activity_id}")
def update_time_block_activity(
    time_block_id: int,
    activity_id: int,
    activity_data: TimeBlockActivityUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
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
    
    # Return manual serialization to avoid Pydantic validation errors
    assigned_students = []
    if hasattr(activity, 'student_assignments'):
        for assignment in activity.student_assignments:
            if assignment.status == 'assigned' and assignment.student:
                first, last = _student_name_parts(assignment.student, auth)
                assigned_students.append({
                    "id": assignment.student.id,
                    "first": first,
                    "last": last,
                    "full_name": _student_display_name(assignment.student, auth)
                })
    
    return {
        "id": activity.id,
        "time_block_id": activity.time_block_id,
        "start_minute": activity.start_minute,
        "duration_minutes": activity.duration_minutes,
        "start_datetime": activity.start_datetime,
        "end_datetime": activity.end_datetime,
        "activity_name": activity.activity_name,
        "activity_type": activity.activity_type,
        "description": activity.description,
        "materials_needed": activity.materials_needed,
        "notes": activity.notes,
        "sequence_order": activity.sequence_order,
        "assigned_student_ids": [s["id"] for s in assigned_students],
        "created_date": activity.created_date,
        "modified_date": activity.modified_date,
        "created_by": activity.created_by,
        "assigned_students": assigned_students
    }


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
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get all appointments for a time block"""
    service = TimeBlockSchedulingService(db)
    appointments = service.get_time_block_appointments(time_block_id)
    
    return [
        {
            "id": apt.id,
            "student_id": apt.student_id,
            "student_name": _student_display_name(apt.student, auth),
            "start_datetime": apt.start_datetime,
            "end_datetime": apt.end_datetime,
            "status": apt.status,
            "has_therapy_session": apt.has_therapy_session,
            "session_status": apt.session_status,
            "series_id": apt.series_id
        }
        for apt in appointments
    ]


@router.get("/time-blocks/{time_block_id}/student-goals")
def get_time_block_student_goals(
    time_block_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get student goal assignments for a time block"""
    from app.models.session_goal import SessionGoal
    from app.models.session_objective import SessionObjective
    from app.models.therapy_session import TherapySession
    from app.models.appointment import Appointment
    from sqlalchemy.orm import joinedload
    
    # Get appointments for this time block with therapy sessions and goals
    appointments = db.query(Appointment).options(
        joinedload(Appointment.student),
        joinedload(Appointment.therapy_session).joinedload(TherapySession.session_goals).joinedload(SessionGoal.goal),
        joinedload(Appointment.therapy_session).joinedload(TherapySession.session_objectives).joinedload(SessionObjective.objective)
    ).filter(Appointment.time_block_id == time_block_id).all()
    
    student_goals = {}
    for appointment in appointments:
        if appointment.therapy_session:
            student_id = appointment.student_id
            if student_id not in student_goals:
                student_goals[student_id] = {
                    "student_id": student_id,
                    "student_name": _student_display_name(appointment.student, auth),
                    "goals": [],
                    "objectives": []
                }
            
            # Add goals
            for session_goal in appointment.therapy_session.session_goals:
                if session_goal.goal:
                    student_goals[student_id]["goals"].append(session_goal.goal.id)
            
            # Add objectives
            for session_objective in appointment.therapy_session.session_objectives:
                if session_objective.objective:
                    student_goals[student_id]["objectives"].append(session_objective.objective.id)
    
    return list(student_goals.values())


# Enhanced time block detail with activities
@router.get("/time-blocks/{time_block_id}/detailed")
def get_time_block_with_activities(
    time_block_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Get a time block with students and activities"""
    
    # Get time block
    time_block_repo = TimeBlockRepository(db)
    time_block = time_block_repo.get_time_block(time_block_id)
    
    if not time_block:
        raise HTTPException(status_code=404, detail="Time block not found")
    
    # Get activities with manual serialization to avoid Pydantic errors
    activity_repo = TimeBlockActivityRepository(db)
    raw_activities = activity_repo.get_activities_by_time_block(time_block_id)
    
    # Manually serialize activities to avoid Student object validation errors
    activities = []
    for activity in raw_activities:
        assigned_students = []
        if hasattr(activity, 'student_assignments'):
            for assignment in activity.student_assignments:
                if assignment.status == 'assigned' and assignment.student:
                    first, last = _student_name_parts(assignment.student, auth)
                    assigned_students.append({
                        "id": assignment.student.id,
                        "first": first,
                        "last": last,
                        "full_name": _student_display_name(assignment.student, auth)
                    })
        
        activity_dict = {
            "id": activity.id,
            "time_block_id": activity.time_block_id,
            "start_minute": activity.start_minute,
            "duration_minutes": activity.duration_minutes,
            "start_datetime": activity.start_datetime,
            "end_datetime": activity.end_datetime,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type,
            "description": activity.description,
            "materials_needed": activity.materials_needed,
            "notes": activity.notes,
            "sequence_order": activity.sequence_order,
            "assigned_student_ids": [s["id"] for s in assigned_students],
            "created_date": activity.created_date,
            "modified_date": activity.modified_date,
            "created_by": activity.created_by,
            "assigned_students": assigned_students
        }
        activities.append(activity_dict)
    
    # Get assigned students
    assigned_students = [
        _student_summary_for_response(assignment.student, auth)
        for assignment in time_block.block_assignments
        if assignment.status == 'assigned'
    ]
    
    # Return as plain dict to avoid Pydantic validation issues
    return {
        **time_block.__dict__,
        "teacher_name": time_block.teacher.full_name if time_block.teacher else None,
        "school_name": time_block.school.name if time_block.school else None,
        "duration_minutes": time_block.duration_minutes,
        "current_student_count": time_block.current_student_count,
        "available_spots": time_block.available_spots,
        "is_full": time_block.is_full,
        "assigned_students": assigned_students,
        "activities": activities
    }


# Activity Student Assignment endpoints
@router.post("/time-blocks/{time_block_id}/activities/{activity_id}/students/{student_id}")
def assign_student_to_activity(
    time_block_id: int,
    activity_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Assign a student to a time block activity"""
    ensure_student_access(auth, student_id, action="assign student to activity")
    repo = TimeBlockActivityRepository(db)
    
    # Verify the activity belongs to the time block
    activity = repo.get_activity(activity_id)
    if not activity or activity.time_block_id != time_block_id:
        raise HTTPException(status_code=404, detail="Activity not found in this time block")
    
    success = repo.assign_student_to_activity(activity_id, student_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to assign student to activity")
    
    return {"message": "Student assigned to activity successfully"}


@router.delete("/time-blocks/{time_block_id}/activities/{activity_id}/students/{student_id}")
def remove_student_from_activity(
    time_block_id: int,
    activity_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Remove a student from a time block activity"""
    ensure_student_access(auth, student_id, action="remove student from activity")
    repo = TimeBlockActivityRepository(db)
    
    # Verify the activity belongs to the time block
    activity = repo.get_activity(activity_id)
    if not activity or activity.time_block_id != time_block_id:
        raise HTTPException(status_code=404, detail="Activity not found in this time block")
    
    success = repo.remove_student_from_activity(activity_id, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student assignment not found")
    
    return {"message": "Student removed from activity successfully"}


@router.put("/activities/series/{series_id}")
def update_activity_series(
    series_id: str,
    activity_updates: List[dict],
    db: Session = Depends(get_db)
):
    """Update activities across all time blocks in a series"""
    logger.info("Activity series update for series %s", series_id)
    logger.debug("Activity updates: %s", activity_updates)
    
    repo = TimeBlockActivityRepository(db)
    
    try:
        result = repo.update_activity_series(series_id, activity_updates)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "Series not found"))
        
        logger.info("Activity series update completed for series %s", series_id)
        logger.debug("Activity series update result: %s", result)
        return result
    except Exception as e:
        # logger.exception carries the traceback, so the bare traceback.print_exc()
        # that used to sit here is redundant.
        logger.exception("Activity series update failed for series %s", series_id)
        raise HTTPException(status_code=500, detail=f"Failed to update activity series: {str(e)}")
