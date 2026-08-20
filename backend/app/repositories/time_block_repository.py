import logging
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from app.models.appointment import Appointment
from app.models.time_block import TimeBlock
from app.models.block_assignment import BlockAssignment
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.school import School
from app.schemas.time_block import TimeBlockCreate, TimeBlockUpdate

from app.services import archive as archive_service

logger = logging.getLogger(__name__)

_WEEKDAY_NAMES = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


class TimeBlockRepository:
    """Group time blocks, their assignments and the appointments they produce.

    ARCHIVE FILTERING. Time blocks are archivable, and so are the appointments
    and therapy sessions a block creates. Every read path here excludes archived
    rows unless `include_archived=True` is passed, including
    `check_teacher_conflict`: an archived block must stop occupying the
    therapist's calendar, for the same reason an archived appointment stops
    occupying its slot.

    BLOCK ASSIGNMENTS ARE NOT ARCHIVED. `block_assignments` is a join row
    between a student and a block; it carries no clinical content and has no
    archive columns. Archiving a block hides the block and its appointments, and
    the membership rows stay exactly as they were -- which is what lets a restore
    put the group back intact instead of reconstructing it. `get_block_students`
    does skip archived STUDENTS, because an archived child is not on the
    caseload the roster is showing.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_time_block(self, time_block_data: TimeBlockCreate) -> TimeBlock:
        """Create a new time block"""
        time_block = TimeBlock(**time_block_data.dict())
        self.db.add(time_block)
        self.db.commit()
        self.db.refresh(time_block)
        return time_block

    def get_time_block(
        self, time_block_id: int, include_archived: bool = False
    ) -> Optional[TimeBlock]:
        """Get time block by ID with related data.

        An archived block reads as absent by default, which turns its id into a
        404 -- the answer a caller used to get after a delete.
        """
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        ).filter(TimeBlock.id == time_block_id)
        if not include_archived:
            query = query.filter(TimeBlock.archived_at.is_(None))
        return query.first()

    def update_time_block(self, time_block_id: int, time_block_data: TimeBlockUpdate) -> Optional[TimeBlock]:
        """Update a time block. An archived block is not editable."""
        time_block = self.db.query(TimeBlock).filter(
            TimeBlock.id == time_block_id,
            TimeBlock.archived_at.is_(None),
        ).first()
        if time_block:
            update_data = time_block_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(time_block, field, value)
            time_block.modified_date = datetime.now()
            self.db.commit()
            self.db.refresh(time_block)
        return time_block

    def get_eligible_students_for_time_block(self, time_block_id: int) -> List[Student]:
        """Get students eligible for assignment to this time block based on teacher/case manager"""
        time_block = self.get_time_block(time_block_id)
        if not time_block:
            return []
        
        # Base query for active students
        query = self.db.query(Student).options(
            joinedload(Student.teacher),
            joinedload(Student.case_manager),
            joinedload(Student.school)
        ).filter(
            and_(
                Student.enrollment_status == 'Active',
                Student.archived_at.is_(None)
            )
        )
        
        # Filter by teacher OR case manager assignment
        if time_block.teacher_id:
            query = query.filter(
                or_(
                    Student.teacher_id == time_block.teacher_id,
                    Student.case_manager_id == time_block.teacher_id
                )
            )
        
        # Exclude students already assigned to this time block
        assigned_student_ids = [assignment.student_id for assignment in time_block.block_assignments 
                              if assignment.status == 'assigned']
        if assigned_student_ids:
            query = query.filter(~Student.id.in_(assigned_student_ids))
        
        return query.order_by(Student.last, Student.first).all()

    def get_time_block_appointments_by_series(self, time_block_id: int) -> dict:
        """Get all appointments for a time block grouped by series_id"""
        from sqlalchemy.orm import joinedload
        
        appointments = self.db.query(Appointment).options(
            joinedload(Appointment.therapy_session),
            joinedload(Appointment.student)
        ).filter(
            Appointment.time_block_id == time_block_id,
            Appointment.archived_at.is_(None),
        ).order_by(Appointment.start_datetime).all()
        
        # Group by series_id
        series_groups = {}
        for appointment in appointments:
            series_id = appointment.series_id
            if series_id not in series_groups:
                series_groups[series_id] = []
            series_groups[series_id].append(appointment)
        
        return {
            "time_block_id": time_block_id,
            "total_appointments": len(appointments),
            "series_groups": series_groups,
            "appointments": appointments
        }

    def create_recurring_time_blocks(self, time_block_data: dict, student_ids: List[int], recurring_config: dict, activities_data: List[dict] = None) -> dict:
        """Create recurring time blocks with appointments for all assigned students"""
        from uuid import uuid4
        from app.models.therapy_session import TherapySession
        from datetime import datetime, timedelta
        
        # Convert string datetime to datetime object
        if isinstance(time_block_data['start_datetime'], str):
            start_datetime = datetime.fromisoformat(time_block_data['start_datetime'])
        else:
            start_datetime = time_block_data['start_datetime']
            
        if isinstance(time_block_data['end_datetime'], str):
            end_datetime = datetime.fromisoformat(time_block_data['end_datetime'])
        else:
            end_datetime = time_block_data['end_datetime']
        
        # Generate all recurring dates
        recurring_dates = self._generate_recurring_dates(
            start_date=start_datetime,
            config=recurring_config
        )
        
        created_time_blocks = []
        created_appointments = []
        conflicts = []
        
        # Generate series ID for this recurring time block series
        series_id = str(uuid4())
        
        # Prepare series metadata
        def make_json_serializable(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            return obj
        
        series_metadata = {
            "recurring_config": make_json_serializable(recurring_config),
            "original_start_datetime": start_datetime.isoformat(),
            "original_end_datetime": end_datetime.isoformat(),
            "total_occurrences": len(recurring_dates),
            "total_students": len(student_ids),
            "created_at": datetime.now().isoformat()
        }
        
        # Calculate time block duration
        duration = end_datetime - start_datetime
        
        for time_block_date in recurring_dates:
            # Calculate start and end times for this occurrence
            block_start = time_block_date
            block_end = block_start + duration
            
            # Create time block for this occurrence
            time_block_dict = time_block_data.copy()
            time_block_dict['start_datetime'] = block_start
            time_block_dict['end_datetime'] = block_end
            
            time_block = TimeBlock(**time_block_dict)
            self.db.add(time_block)
            self.db.flush()  # Get time block ID
            
            created_time_blocks.append(time_block)
            
            # Assign students and create appointments for this time block
            for student_id in student_ids:
                # First assign the student
                success = self.assign_student_to_block(time_block.id, student_id)
                if not success:
                    conflicts.append(f"Failed to assign student {student_id} to time block {time_block_date}")
                    continue
            
            # Calculate time slots for all students in this time block
            time_slots = time_block.calculate_student_time_slots()
            
            # Create appointments for each student
            for slot in time_slots:
                student = slot['student']
                start_time = slot['start_datetime']
                end_time = slot['end_datetime']
                
                # Create appointment with series support
                appointment = Appointment(
                    student_id=student.id,
                    teacher_id=time_block.teacher_id,
                    school_id=time_block.school_id,
                    time_block_id=time_block.id,
                    start_datetime=start_time,
                    end_datetime=end_time,
                    appointment_type='group',
                    status='scheduled',
                    location=time_block.location,
                    notes=f"Recurring time block: {time_block.title}",
                    series_id=series_id
                )
                appointment.set_series_config(series_metadata)
                self.db.add(appointment)
                self.db.flush()  # Get appointment ID
                
                # Create therapy session with series support
                therapy_session = TherapySession(
                    student_id=student.id,
                    appointment_id=appointment.id,
                    time_block_id=time_block.id,
                    session_date=start_time,
                    start_time=start_time,
                    end_time=end_time,
                    planned_duration_minutes=slot['duration_minutes'],
                    session_type='group',
                    status='planned',
                    created_from='time_block',
                    series_id=series_id
                )
                therapy_session.set_series_config(series_metadata)
                self.db.add(therapy_session)
                
                created_appointments.append(appointment)
            
            # Create activities for this time block if provided
            if activities_data:
                from app.models.time_block_activity import TimeBlockActivity
                from app.models.activity_student_assignment import ActivityStudentAssignment
                
                for activity_data in activities_data:
                    logger.debug(
                        "Creating activity %r for time block %s",
                        activity_data.get('activity_name'),
                        time_block.id,
                    )
                    
                    # Create activity (ignore the time_block_id from frontend, use the current time block)
                    activity = TimeBlockActivity(
                        time_block_id=time_block.id,  # Use the current time block ID, not from frontend
                        start_minute=activity_data.get('start_minute', 0),
                        duration_minutes=activity_data.get('duration_minutes', 5),
                        activity_name=activity_data.get('activity_name', ''),
                        activity_type=activity_data.get('activity_type'),
                        description=activity_data.get('description'),
                        materials_needed=activity_data.get('materials_needed'),
                        notes=activity_data.get('notes'),
                        sequence_order=activity_data.get('sequence_order', 1)
                    )
                    
                    # Set datetime fields if provided
                    if activity_data.get('start_datetime'):
                        activity.start_datetime = datetime.fromisoformat(activity_data['start_datetime'])
                    if activity_data.get('end_datetime'):
                        activity.end_datetime = datetime.fromisoformat(activity_data['end_datetime'])
                    
                    self.db.add(activity)
                    self.db.flush()  # Get activity ID and ensure time_block relationship is loaded
                    
                    # Refresh to load the time_block relationship
                    self.db.refresh(activity)
                    
                    # Now sync datetime with minutes for this time block
                    if activity.start_datetime and activity.end_datetime:
                        activity.sync_minutes_with_datetime()
                    else:
                        activity.sync_datetime_with_minutes()
                    
                    # Commit the datetime updates
                    self.db.flush()
                    
                    # Create student assignments for this activity
                    assigned_student_ids = activity_data.get('assigned_student_ids', [])
                    for student_id in assigned_student_ids:
                        if student_id in student_ids:  # Only assign students that are in the time block
                            assignment = ActivityStudentAssignment(
                                activity_id=activity.id,
                                student_id=student_id,
                                status='assigned',
                                created_date=datetime.now(),
                                modified_date=datetime.now()
                            )
                            self.db.add(assignment)
        
        self.db.commit()
        
        return {
            "time_blocks_created": created_time_blocks,
            "appointments_created": created_appointments,
            "conflicts": conflicts,
            "total_time_blocks": len(created_time_blocks),
            "total_appointments": len(created_appointments),
            "total_conflicts": len(conflicts),
            "series_id": series_id,
            "schedule_dates": [tb.start_datetime for tb in created_time_blocks]
        }

    def _generate_recurring_dates(self, start_date: datetime, config: dict) -> List[datetime]:
        """Generate recurring dates based on configuration - copied from appointment repository"""
        from datetime import timedelta
        
        dates = []
        current_date = start_date
        
        frequency = config.get('frequency', 'weekly')
        interval = config.get('interval', 1)
        end_type = config.get('end_type', 'count')
        
        if frequency == 'weekly':
            days_of_week = config.get('days_of_week', [start_date.weekday()])
            
            if end_type == 'date':
                end_date = config.get('end_date')
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                week_start = current_date - timedelta(days=current_date.weekday())
                
                while current_date <= end_date:
                    for day_of_week in days_of_week:
                        occurrence_date = week_start + timedelta(days=day_of_week)
                        occurrence_datetime = occurrence_date.replace(
                            hour=start_date.hour,
                            minute=start_date.minute,
                            second=start_date.second,
                            microsecond=start_date.microsecond
                        )
                        
                        if occurrence_datetime >= start_date and occurrence_datetime <= end_date:
                            dates.append(occurrence_datetime)
                    
                    week_start += timedelta(weeks=interval)
                    current_date = week_start
            
            elif end_type == 'count':
                max_occurrences = config.get('max_occurrences', 10)
                week_start = current_date - timedelta(days=current_date.weekday())
                
                while len(dates) < max_occurrences:
                    for day_of_week in days_of_week:
                        if len(dates) >= max_occurrences:
                            break
                        
                        occurrence_date = week_start + timedelta(days=day_of_week)
                        occurrence_datetime = occurrence_date.replace(
                            hour=start_date.hour,
                            minute=start_date.minute,
                            second=start_date.second,
                            microsecond=start_date.microsecond
                        )
                        
                        if occurrence_datetime >= start_date:
                            dates.append(occurrence_datetime)
                    
                    week_start += timedelta(weeks=interval)
        
        return sorted(dates)

    def update_time_block_series(self, series_id: str, update_data: dict) -> dict:
        """Update all time blocks in a series with smart time slot recalculation"""
        from app.models.therapy_session import TherapySession
        from uuid import uuid4
        
        # Get all appointments in this series
        appointments = self.db.query(Appointment).options(
            joinedload(Appointment.therapy_session),
            joinedload(Appointment.student)
        ).filter(
            and_(
                Appointment.series_id == series_id,
                Appointment.time_block_id.isnot(None),
                Appointment.archived_at.is_(None)
            )
        ).order_by(Appointment.start_datetime).all()
        
        if not appointments:
            return {"success": False, "message": "No time block appointments found for this series"}
        
        # Group appointments by time block
        time_block_groups = {}
        for appointment in appointments:
            tb_id = appointment.time_block_id
            if tb_id not in time_block_groups:
                time_block_groups[tb_id] = []
            time_block_groups[tb_id].append(appointment)
        
        updated_time_blocks = []
        updated_appointments = []
        
        # Determine if we need to recalculate time slots
        needs_time_recalculation = False
        if update_data.get('start_datetime') and update_data.get('end_datetime'):
            # Check if the duration changed
            new_start = datetime.fromisoformat(update_data['start_datetime'])
            new_end = datetime.fromisoformat(update_data['end_datetime'])
            new_duration = (new_end - new_start).total_seconds() / 60
            
            # Get first time block to compare duration
            first_appointment = appointments[0]
            first_time_block = self.get_time_block(first_appointment.time_block_id)
            if first_time_block:
                old_duration = first_time_block.duration_minutes
                if abs(new_duration - old_duration) > 1:  # Allow 1-minute tolerance
                    needs_time_recalculation = True
        
        logger.debug("Time block series update: needs_time_recalculation=%s", needs_time_recalculation)
        
        # Update each time block and its appointments
        for time_block_id, block_appointments in time_block_groups.items():
            # Skip if no appointments need updating
            editable_appointments = [apt for apt in block_appointments 
                                   if not apt.therapy_session or apt.therapy_session.status not in ['completed', 'in_progress']]
            
            if not editable_appointments:
                continue
                
            # Get the time block
            time_block = self.get_time_block(time_block_id)
            if not time_block:
                continue
            
            # Update time block properties
            if update_data.get('title'):
                time_block.title = update_data['title']
            if update_data.get('location'):
                time_block.location = update_data['location']
            if update_data.get('notes'):
                time_block.notes = update_data['notes']
            if update_data.get('am_pm_indicator'):
                time_block.am_pm_indicator = update_data['am_pm_indicator']
            
            # Update time block times if provided
            if update_data.get('start_datetime') and update_data.get('end_datetime'):
                new_start = datetime.fromisoformat(update_data['start_datetime'])
                new_end = datetime.fromisoformat(update_data['end_datetime'])
                
                # Apply time changes to existing date (preserve the date, update time)
                time_block.start_datetime = time_block.start_datetime.replace(
                    hour=new_start.hour, 
                    minute=new_start.minute, 
                    second=0, 
                    microsecond=0
                )
                time_block.end_datetime = time_block.end_datetime.replace(
                    hour=new_end.hour, 
                    minute=new_end.minute, 
                    second=0, 
                    microsecond=0
                )
            
            time_block.modified_date = datetime.now()
            updated_time_blocks.append(time_block)
            
            # Update appointments
            if needs_time_recalculation:
                # Recalculate time slots and update each appointment
                time_slots = time_block.calculate_student_time_slots()
                
                for slot in time_slots:
                    student = slot['student']
                    new_start_time = slot['start_datetime']
                    new_end_time = slot['end_datetime']
                    
                    # Find the appointment for this student
                    appointment = next((apt for apt in editable_appointments if apt.student_id == student.id), None)
                    if appointment:
                        appointment.start_datetime = new_start_time
                        appointment.end_datetime = new_end_time
                        
                        # Update therapy session
                        if appointment.therapy_session:
                            appointment.therapy_session.session_date = new_start_time
                            appointment.therapy_session.start_time = new_start_time
                            appointment.therapy_session.end_time = new_end_time
                            appointment.therapy_session.planned_duration_minutes = slot['duration_minutes']
                        
                        updated_appointments.append(appointment)
            else:
                # Just update non-time fields and preserve relative time slots
                for appointment in editable_appointments:
                    if update_data.get('notes'):
                        appointment.notes = f"Recurring time block: {time_block.title}"
                    
                    # Update therapy session notes if applicable
                    if appointment.therapy_session and update_data.get('notes'):
                        appointment.therapy_session.prep_notes = update_data.get('notes')
                    
                    updated_appointments.append(appointment)
        
        self.db.commit()
        
        return {
            "success": True,
            "message": f"Updated {len(updated_time_blocks)} time blocks and {len(updated_appointments)} appointments",
            "updated_time_blocks": len(updated_time_blocks),
            "updated_appointments": len(updated_appointments),
            "recalculated_time_slots": needs_time_recalculation
        }

    def update_time_block_series_pattern(self, series_id: str, pattern_data: dict) -> dict:
        """Update time block series with pattern changes (date shifts, day alignment)"""
        from app.models.therapy_session import TherapySession
        from datetime import timedelta
        
        logger.info("Time block series pattern update for series %s", series_id)
        logger.debug("Pattern data: %s", pattern_data)
        
        # Get all appointments in this series that belong to time blocks
        appointments = self.db.query(Appointment).options(
            joinedload(Appointment.therapy_session),
            joinedload(Appointment.student)
        ).filter(
            and_(
                Appointment.series_id == series_id,
                Appointment.time_block_id.isnot(None),
                Appointment.archived_at.is_(None)
            )
        ).order_by(Appointment.start_datetime).all()
        
        if not appointments:
            return {"success": False, "message": "No time block appointments found for this series"}
        
        logger.debug("Found %d appointments in series", len(appointments))
        
        # Filter out completed/in-progress sessions
        editable_appointments = []
        for appointment in appointments:
            should_update = True
            if appointment.therapy_session:
                session_status = appointment.therapy_session.status
                if session_status in ['completed', 'in_progress']:
                    should_update = False
            elif appointment.start_datetime < datetime.now():
                should_update = False
            
            if should_update:
                editable_appointments.append(appointment)
        
        logger.debug("Found %d editable appointments", len(editable_appointments))
        
        if not editable_appointments:
            return {"success": False, "message": "No editable appointments found in series"}
        
        # Group by time block
        time_block_groups = {}
        for appointment in editable_appointments:
            tb_id = appointment.time_block_id
            if tb_id not in time_block_groups:
                time_block_groups[tb_id] = []
            time_block_groups[tb_id].append(appointment)
        
        updated_time_blocks = []
        updated_appointments = []
        
        # Process each time block
        for time_block_id, block_appointments in time_block_groups.items():
            time_block = self.get_time_block(time_block_id)
            if not time_block:
                continue
            
            logger.debug(
                "Processing time block %s with %d appointments",
                time_block_id,
                len(block_appointments),
            )
            
            # Calculate new time block date based on pattern
            update_type = pattern_data.get('update_type', 'day_alignment')
            
            if update_type == 'offset_only':
                # Apply simple offset
                offset_days = pattern_data.get('date_offset_days', 0)
                offset_delta = timedelta(days=offset_days)
                new_block_start = time_block.start_datetime + offset_delta
                new_block_end = time_block.end_datetime + offset_delta
                
            elif update_type == 'day_alignment':
                # Apply offset then align to target day of week
                offset_days = pattern_data.get('date_offset_days', 0)
                target_day = pattern_data.get('target_day_of_week', 1)  # Default to Monday
                
                logger.debug(
                    "Day alignment: offset_days=%s, target_day=%s, original date %s (weekday %d)",
                    offset_days,
                    target_day,
                    time_block.start_datetime.date(),
                    time_block.start_datetime.weekday(),
                )
                
                # Apply offset first
                offset_date = time_block.start_datetime.date() + timedelta(days=offset_days)
                logger.debug("After offset: %s (weekday %d)", offset_date, offset_date.weekday())
                
                # Find next occurrence of target day of week
                current_day = offset_date.weekday()  # Monday = 0, Tuesday = 1, etc.
                
                # target_day comes from frontend as Sunday=0 system, convert to Monday=0 system
                if target_day == 0:  # Sunday
                    target_weekday = 6
                else:  # Monday=1 becomes 0, Tuesday=2 becomes 1, etc.
                    target_weekday = target_day - 1
                
                logger.debug(
                    "Current weekday: %d (%s), target weekday: %d (%s)",
                    current_day,
                    _WEEKDAY_NAMES[current_day],
                    target_weekday,
                    _WEEKDAY_NAMES[target_weekday],
                )
                
                days_to_add = (target_weekday - current_day) % 7
                if days_to_add == 0 and current_day != target_weekday:
                    days_to_add = 7  # Move to next week if already on target day
                
                
                aligned_date = offset_date + timedelta(days=days_to_add)
                logger.debug(
                    "Days to add: (%d - %d) %% 7 = %d, final date: %s",
                    target_weekday,
                    current_day,
                    days_to_add,
                    aligned_date,
                )
                
                # Keep original times
                original_start_time = time_block.start_datetime.time()
                original_end_time = time_block.end_datetime.time()
                
                new_block_start = datetime.combine(aligned_date, original_start_time)
                new_block_end = datetime.combine(aligned_date, original_end_time)
                
            else:
                # Default: no date change, just time updates
                new_block_start = time_block.start_datetime
                new_block_end = time_block.end_datetime
                
                if pattern_data.get('start_datetime') and pattern_data.get('end_datetime'):
                    new_start_dt = datetime.fromisoformat(pattern_data['start_datetime'])
                    new_end_dt = datetime.fromisoformat(pattern_data['end_datetime'])
                    
                    new_block_start = new_block_start.replace(
                        hour=new_start_dt.hour,
                        minute=new_start_dt.minute,
                        second=0,
                        microsecond=0
                    )
                    new_block_end = new_block_end.replace(
                        hour=new_end_dt.hour,
                        minute=new_end_dt.minute,
                        second=0,
                        microsecond=0
                    )
            
            logger.debug(
                "Time block %s: %s to %s",
                time_block_id,
                time_block.start_datetime,
                new_block_start,
            )
            
            # Update time block
            time_block.start_datetime = new_block_start
            time_block.end_datetime = new_block_end
            time_block.modified_date = datetime.now()
            
            # Update other fields if provided
            if pattern_data.get('title'):
                time_block.title = pattern_data['title']
            if pattern_data.get('location'):
                time_block.location = pattern_data['location']
            if pattern_data.get('notes'):
                time_block.notes = pattern_data['notes']
            
            updated_time_blocks.append(time_block)
            
            # Recalculate time slots for this updated time block
            time_slots = time_block.calculate_student_time_slots()
            
            # Update each appointment with new calculated times
            for slot in time_slots:
                student = slot['student']
                new_start_time = slot['start_datetime']
                new_end_time = slot['end_datetime']
                
                # Find the appointment for this student
                appointment = next((apt for apt in block_appointments if apt.student_id == student.id), None)
                if appointment:
                    logger.debug(
                        "Updating appointment %s: %s to %s",
                        appointment.id,
                        appointment.start_datetime,
                        new_start_time,
                    )
                    
                    appointment.start_datetime = new_start_time
                    appointment.end_datetime = new_end_time
                    
                    # Update notes if provided
                    if pattern_data.get('notes'):
                        appointment.notes = f"Recurring time block: {time_block.title}"
                    
                    # Update therapy session
                    if appointment.therapy_session:
                        appointment.therapy_session.session_date = new_start_time
                        appointment.therapy_session.start_time = new_start_time
                        appointment.therapy_session.end_time = new_end_time
                        appointment.therapy_session.planned_duration_minutes = slot['duration_minutes']
                        
                        if pattern_data.get('notes'):
                            appointment.therapy_session.prep_notes = pattern_data['notes']
                    
                    updated_appointments.append(appointment)
        
        self.db.commit()
        
        logger.info(
            "Updated %d time blocks and %d appointments",
            len(updated_time_blocks),
            len(updated_appointments),
        )
        
        return {
            "success": True,
            "message": f"Updated {len(updated_time_blocks)} time blocks and {len(updated_appointments)} appointments",
            "updated_time_blocks": len(updated_time_blocks),
            "updated_appointments": len(updated_appointments),
            "time_blocks": updated_time_blocks,
            "appointments": updated_appointments
        }

    def assign_student_with_auto_scheduling(self, time_block_id: int, student_id: int, auto_create_appointments: bool = True) -> dict:
        """Assign student to time block and optionally auto-create appointments with time splitting"""
        from app.models.therapy_session import TherapySession
        from uuid import uuid4
        
        # First, assign the student normally
        success = self.assign_student_to_block(time_block_id, student_id)
        if not success:
            return {"success": False, "message": "Failed to assign student to time block"}
        
        if not auto_create_appointments:
            return {"success": True, "message": "Student assigned successfully"}
        
        # Get the updated time block with all assignments
        time_block = self.get_time_block(time_block_id)
        if not time_block:
            return {"success": False, "message": "Time block not found"}
        
        # Calculate time slots for all students
        time_slots = time_block.calculate_student_time_slots()
        
        # Create or update appointments for each student
        created_appointments = []
        updated_appointments = []
        
        for slot in time_slots:
            student = slot['student']
            start_time = slot['start_datetime']
            end_time = slot['end_datetime']
            
            # Check if appointment already exists for this student in this time block
            existing_appointment = self.db.query(Appointment).filter(
                and_(
                    Appointment.student_id == student.id,
                    Appointment.time_block_id == time_block_id,
                    # An archived appointment is not "existing" -- reusing it
                    # would resurrect a row the therapist took off the calendar.
                    Appointment.archived_at.is_(None)
                )
            ).first()
            
            if existing_appointment:
                # Update existing appointment with new times
                existing_appointment.start_datetime = start_time
                existing_appointment.end_datetime = end_time
                existing_appointment.teacher_id = time_block.teacher_id
                existing_appointment.school_id = time_block.school_id
                existing_appointment.location = time_block.location
                
                # Update associated therapy session
                if existing_appointment.therapy_session:
                    therapy_session = existing_appointment.therapy_session
                    therapy_session.session_date = start_time
                    therapy_session.start_time = start_time
                    therapy_session.end_time = end_time
                    therapy_session.planned_duration_minutes = slot['duration_minutes']
                
                updated_appointments.append(existing_appointment)
            else:
                # Create new appointment
                appointment = Appointment(
                    student_id=student.id,
                    teacher_id=time_block.teacher_id,
                    school_id=time_block.school_id,
                    time_block_id=time_block_id,
                    start_datetime=start_time,
                    end_datetime=end_time,
                    appointment_type='group',
                    status='scheduled',
                    location=time_block.location,
                    notes=f"Auto-generated from time block: {time_block.title}"
                )
                self.db.add(appointment)
                self.db.flush()  # Get appointment ID
                
                # Create therapy session
                therapy_session = TherapySession(
                    student_id=student.id,
                    appointment_id=appointment.id,
                    time_block_id=time_block_id,
                    session_date=start_time,
                    start_time=start_time,
                    end_time=end_time,
                    planned_duration_minutes=slot['duration_minutes'],
                    session_type='group',
                    status='planned',
                    created_from='time_block'
                )
                self.db.add(therapy_session)
                created_appointments.append(appointment)
        
        self.db.commit()
        
        return {
            "success": True,
            "message": f"Student assigned and {len(created_appointments)} appointments created, {len(updated_appointments)} updated",
            "created_appointments": len(created_appointments),
            "updated_appointments": len(updated_appointments),
            "time_slots": time_slots
        }

    def remove_student_with_auto_rescheduling(self, time_block_id: int, student_id: int, auto_update_appointments: bool = True) -> dict:
        """Remove student from time block and optionally recalculate remaining appointments"""
        from uuid import uuid4
        
        # First, remove the student normally
        success = self.remove_student_from_block(time_block_id, student_id)
        if not success:
            return {"success": False, "message": "Failed to remove student from time block"}
        
        if not auto_update_appointments:
            return {"success": True, "message": "Student removed successfully"}
        
        # Get the updated time block
        time_block = self.get_time_block(time_block_id)
        if not time_block:
            return {"success": False, "message": "Time block not found"}
        
        # Recalculate time slots for remaining students
        time_slots = time_block.calculate_student_time_slots()
        
        # Update existing appointments with new times
        updated_appointments = []
        for slot in time_slots:
            student = slot['student']
            start_time = slot['start_datetime']
            end_time = slot['end_datetime']
            
            # Find existing appointment for this student
            existing_appointment = self.db.query(Appointment).filter(
                and_(
                    Appointment.student_id == student.id,
                    Appointment.time_block_id == time_block_id,
                    # An archived appointment is not "existing" -- reusing it
                    # would resurrect a row the therapist took off the calendar.
                    Appointment.archived_at.is_(None)
                )
            ).first()
            
            if existing_appointment:
                # Update appointment times
                existing_appointment.start_datetime = start_time
                existing_appointment.end_datetime = end_time
                
                # Update associated therapy session
                if existing_appointment.therapy_session:
                    therapy_session = existing_appointment.therapy_session
                    therapy_session.session_date = start_time
                    therapy_session.start_time = start_time
                    therapy_session.end_time = end_time
                    therapy_session.planned_duration_minutes = slot['duration_minutes']
                
                updated_appointments.append(existing_appointment)
        
        self.db.commit()
        
        return {
            "success": True,
            "message": f"Student removed and {len(updated_appointments)} appointments updated",
            "updated_appointments": len(updated_appointments),
            "time_slots": time_slots
        }

    def archive_time_block(
        self, time_block_id: int, user_id: int, reason: Optional[str] = None
    ) -> Optional["archive_service.ArchiveEvent"]:
        """Archive a time block with its appointments and therapy sessions.

        Replaces `delete_time_block`, which walked exactly this set and
        destroyed it. The cascade lives in `app.services.archive` so that this
        method, the DELETE route and any future caller cannot disagree about
        what a block "contains".

        Block assignments and activities are left in place -- see the class
        docstring. They were only deleted before because a foreign key forced
        it, and keeping them is what lets a restore hand the group back whole.

        Returns None when there is no such (active) block.
        """
        time_block = self.db.query(TimeBlock).filter(
            TimeBlock.id == time_block_id,
            TimeBlock.archived_at.is_(None),
        ).first()
        if not time_block:
            return None

        logger.info("Archiving time block %s and its appointments", time_block_id)
        event = archive_service.archive(
            self.db,
            user_id=user_id,
            entity_type=archive_service.ENTITY_TIME_BLOCK,
            entity_id=time_block_id,
            reason=reason,
        )
        logger.info(
            "Archived time block %s under archive event %s", time_block_id, event.id
        )
        return event

    def get_time_blocks_by_date_range(
        self,
        start_date: date,
        end_date: date,
        teacher_id: Optional[int] = None,
        school_id: Optional[int] = None,
        block_type: Optional[str] = None,
        status: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[TimeBlock]:
        """Get time blocks within a date range with optional filters"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        )

        if not include_archived:
            query = query.filter(TimeBlock.archived_at.is_(None))

        # Date range filter
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(
            and_(
                TimeBlock.start_datetime >= start_datetime,
                TimeBlock.start_datetime <= end_datetime
            )
        )

        # Optional filters
        if teacher_id:
            query = query.filter(TimeBlock.teacher_id == teacher_id)
        if school_id:
            query = query.filter(TimeBlock.school_id == school_id)
        if block_type:
            query = query.filter(TimeBlock.block_type == block_type)
        if status:
            query = query.filter(TimeBlock.status == status)

        return query.order_by(TimeBlock.start_datetime).all()

    def get_teacher_time_blocks(
        self,
        teacher_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_archived: bool = False,
    ) -> List[TimeBlock]:
        """Get all time blocks for a specific teacher"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        ).filter(TimeBlock.teacher_id == teacher_id)

        if not include_archived:
            query = query.filter(TimeBlock.archived_at.is_(None))

        if start_date and end_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(
                and_(
                    TimeBlock.start_datetime >= start_datetime,
                    TimeBlock.start_datetime <= end_datetime
                )
            )

        return query.order_by(TimeBlock.start_datetime).all()

    def get_available_time_blocks(
        self,
        start_date: date,
        end_date: date,
        school_id: Optional[int] = None,
        block_type: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[TimeBlock]:
        """Get time blocks that have available spots"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        )

        if not include_archived:
            query = query.filter(TimeBlock.archived_at.is_(None))

        # Date range filter
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(
            and_(
                TimeBlock.start_datetime >= start_datetime,
                TimeBlock.start_datetime <= end_datetime,
                TimeBlock.status == 'active'
            )
        )

        # Optional filters
        if school_id:
            query = query.filter(TimeBlock.school_id == school_id)
        if block_type:
            query = query.filter(TimeBlock.block_type == block_type)

        time_blocks = query.order_by(TimeBlock.start_datetime).all()
        
        # Filter out full blocks
        available_blocks = []
        for block in time_blocks:
            if not block.is_full:
                available_blocks.append(block)
        
        return available_blocks

    def check_teacher_conflict(
        self,
        teacher_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_block_id: Optional[int] = None
    ) -> bool:
        """Check if teacher has conflicting time blocks in the time slot.

        SCHEDULING DECISION: archived blocks never conflict -- see the class
        docstring.
        """
        query = self.db.query(TimeBlock).filter(
            and_(
                TimeBlock.teacher_id == teacher_id,
                TimeBlock.archived_at.is_(None),
                TimeBlock.status.in_(['active']),
                or_(
                    # New block starts during existing block
                    and_(
                        TimeBlock.start_datetime <= start_datetime,
                        TimeBlock.end_datetime > start_datetime
                    ),
                    # New block ends during existing block
                    and_(
                        TimeBlock.start_datetime < end_datetime,
                        TimeBlock.end_datetime >= end_datetime
                    ),
                    # New block completely contains existing block
                    and_(
                        TimeBlock.start_datetime >= start_datetime,
                        TimeBlock.end_datetime <= end_datetime
                    )
                )
            )
        )

        if exclude_block_id:
            query = query.filter(TimeBlock.id != exclude_block_id)

        return query.first() is not None

    def assign_student_to_block(self, time_block_id: int, student_id: int) -> bool:
        """Assign a student to a time block"""
        time_block = self.get_time_block(time_block_id)
        if not time_block or time_block.is_full:
            return False

        # Check if student is already assigned
        existing_assignment = self.db.query(BlockAssignment).filter(
            and_(
                BlockAssignment.time_block_id == time_block_id,
                BlockAssignment.student_id == student_id,
                BlockAssignment.status == 'assigned'
            )
        ).first()

        if existing_assignment:
            return False

        # Create new assignment
        assignment = BlockAssignment(
            time_block_id=time_block_id,
            student_id=student_id,
            status='assigned',
            assignment_date=datetime.now()
        )
        self.db.add(assignment)
        self.db.commit()
        return True

    def remove_student_from_block(self, time_block_id: int, student_id: int) -> bool:
        """Remove a student from a time block"""
        assignment = self.db.query(BlockAssignment).filter(
            and_(
                BlockAssignment.time_block_id == time_block_id,
                BlockAssignment.student_id == student_id,
                BlockAssignment.status == 'assigned'
            )
        ).first()

        if assignment:
            assignment.status = 'removed'
            assignment.removed_date = datetime.now()
            assignment.modified_date = datetime.now()
            self.db.commit()
            return True
        return False

    def get_block_students(
        self, time_block_id: int, include_archived: bool = False
    ) -> List[Student]:
        """Get all students assigned to a time block.

        The ASSIGNMENT rows are never archived (see the class docstring); the
        archived STUDENTS behind them are filtered out here, because an archived
        child is not on the caseload this roster is showing.
        """
        query = self.db.query(BlockAssignment).join(
            Student, BlockAssignment.student_id == Student.id
        ).options(
            joinedload(BlockAssignment.student)
        ).filter(
            and_(
                BlockAssignment.time_block_id == time_block_id,
                BlockAssignment.status == 'assigned'
            )
        )
        if not include_archived:
            query = query.filter(Student.archived_at.is_(None))

        return [assignment.student for assignment in query.all()]
