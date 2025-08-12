from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from app.models.appointment import Appointment
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.school import School
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, RecurringAppointmentCreate


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_appointment(self, appointment_data: AppointmentCreate) -> Appointment:
        """Create a new appointment with optional therapy session planning"""
        from app.models.therapy_session import TherapySession
        from app.models.session_goal import SessionGoal
        from app.models.session_objective import SessionObjective
        
        # Extract goal/objective planning data
        planned_goals = appointment_data.planned_goals
        planned_objectives = appointment_data.planned_objectives
        
        print(f"🎯 Backend debug - planned_goals: {planned_goals}")
        print(f"📋 Backend debug - planned_objectives: {planned_objectives}")
        
        # Create appointment (exclude the planning fields)
        appointment_dict = appointment_data.dict(exclude={'planned_goals', 'planned_objectives'})
        appointment = Appointment(**appointment_dict)
        self.db.add(appointment)
        self.db.flush()  # Flush to get the appointment ID
        
        # Always create a therapy session for every appointment
        therapy_session = TherapySession(
            student_id=appointment.student_id,
            appointment_id=appointment.id,
            session_date=appointment.start_datetime,  # Pass full datetime
            start_time=appointment.start_datetime,     # Pass full datetime
            end_time=appointment.end_datetime,         # Pass full datetime
            planned_duration_minutes=int((appointment.end_datetime - appointment.start_datetime).total_seconds() / 60),
            session_type='individual',
            status='planned',
            created_from='appointment',
            goals_addressed=True if (planned_goals or planned_objectives) else False
        )
        self.db.add(therapy_session)
        self.db.flush()  # Flush to get the therapy session ID
        
        # Add planned goals if provided
        if planned_goals:
            print(f"🎯 Creating {len(planned_goals)} session goals for therapy_session_id={therapy_session.id}")
            for i, goal_data in enumerate(planned_goals):
                print(f"  Goal {i+1}: goal_id={goal_data.goal_id}, planned={goal_data.planned}")
                session_goal = SessionGoal(
                    therapy_session_id=therapy_session.id,
                    goal_id=goal_data.goal_id,
                    planned=goal_data.planned,
                    worked_on=goal_data.worked_on,
                    priority=goal_data.priority
                )
                self.db.add(session_goal)
        else:
            print("🎯 No planned goals - therapy session created without goals")
        
        # Add planned objectives if provided
        if planned_objectives:
            print(f"📋 Creating {len(planned_objectives)} session objectives for therapy_session_id={therapy_session.id}")
            for i, objective_data in enumerate(planned_objectives):
                print(f"  Objective {i+1}: objective_id={objective_data.objective_id}, goal_id={objective_data.goal_id}, planned={objective_data.planned}")
                session_objective = SessionObjective(
                    therapy_session_id=therapy_session.id,
                    objective_id=objective_data.objective_id,
                    goal_id=objective_data.goal_id,
                    planned=objective_data.planned,
                    worked_on=objective_data.worked_on,
                    priority=objective_data.priority,
                    pre_session_notes=objective_data.pre_session_notes
                )
                self.db.add(session_objective)
        else:
            print("📋 No planned objectives - therapy session created without objectives")
        
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def create_recurring_appointments(self, recurring_data: RecurringAppointmentCreate) -> dict:
        """Create recurring appointments with same therapy session planning as single appointments"""
        from datetime import datetime, timedelta
        import uuid
        from app.models.therapy_session import TherapySession
        from app.models.session_goal import SessionGoal
        from app.models.session_objective import SessionObjective
        
        # Generate all recurring dates
        recurring_dates = self._generate_recurring_dates(
            start_date=recurring_data.start_datetime,
            config=recurring_data.recurring_config
        )
        
        created_appointments = []
        conflicts = []
        
        # Generate series ID for this recurring appointment series
        series_id = str(uuid.uuid4())
        
        # Prepare series metadata (ensure all values are JSON serializable)
        recurring_config_dict = recurring_data.recurring_config.dict()
        
        # Convert any datetime objects in recurring_config to ISO format
        def make_json_serializable(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            return obj
        
        series_metadata = {
            "recurring_config": make_json_serializable(recurring_config_dict),
            "original_start_datetime": recurring_data.start_datetime.isoformat(),
            "original_end_datetime": recurring_data.end_datetime.isoformat(),
            "total_occurrences": len(recurring_dates),
            "created_at": datetime.now().isoformat()
        }
        
        # Calculate appointment duration
        duration = recurring_data.end_datetime - recurring_data.start_datetime
        
        for appointment_date in recurring_dates:
            # Calculate start and end times for this occurrence
            appointment_start = appointment_date
            appointment_end = appointment_start + duration
            
            # Check for conflicts
            if self.check_time_conflict(
                student_id=recurring_data.student_id,
                start_datetime=appointment_start,
                end_datetime=appointment_end
            ):
                conflicts.append(f"Conflict at {appointment_start.strftime('%Y-%m-%d %H:%M')}")
                continue
            
            # Create appointment data for this occurrence
            appointment_dict = recurring_data.dict(exclude={'recurring_config', 'planned_goals', 'planned_objectives'})
            appointment_dict['start_datetime'] = appointment_start
            appointment_dict['end_datetime'] = appointment_end
            appointment_dict['series_id'] = series_id
            
            # Create the appointment
            appointment = Appointment(**appointment_dict)
            appointment.set_series_config(series_metadata)  # Use the model method for proper JSON formatting
            self.db.add(appointment)
            self.db.flush()  # Get appointment ID
            
            # Always create therapy session for every appointment
            therapy_session = TherapySession(
                student_id=appointment.student_id,
                appointment_id=appointment.id,
                session_date=appointment.start_datetime,
                start_time=appointment.start_datetime,
                end_time=appointment.end_datetime,
                planned_duration_minutes=int(duration.total_seconds() / 60),
                session_type='individual',
                status='planned',
                created_from='appointment',
                goals_addressed=True if (recurring_data.planned_goals or recurring_data.planned_objectives) else False,
                series_id=series_id
            )
            therapy_session.set_series_config(series_metadata)  # Add series metadata to therapy session
            self.db.add(therapy_session)
            self.db.flush()  # Get therapy session ID
            
            # Add planned goals if provided (same as single appointment)
            if recurring_data.planned_goals:
                for goal_data in recurring_data.planned_goals:
                    session_goal = SessionGoal(
                        therapy_session_id=therapy_session.id,
                        goal_id=goal_data.goal_id,
                        planned=goal_data.planned,
                        worked_on=goal_data.worked_on,
                        priority=goal_data.priority
                    )
                    self.db.add(session_goal)
            
            # Add planned objectives if provided (same as single appointment)
            if recurring_data.planned_objectives:
                for objective_data in recurring_data.planned_objectives:
                    session_objective = SessionObjective(
                        therapy_session_id=therapy_session.id,
                        objective_id=objective_data.objective_id,
                        goal_id=objective_data.goal_id,
                        planned=objective_data.planned,
                        worked_on=objective_data.worked_on,
                        priority=objective_data.priority,
                        pre_session_notes=objective_data.pre_session_notes
                    )
                    self.db.add(session_objective)
            
            created_appointments.append(appointment)
        
        # Commit all changes
        self.db.commit()
        
        # Refresh all appointments
        for appointment in created_appointments:
            self.db.refresh(appointment)
        
        return {
            'appointments': created_appointments,
            'total_created': len(created_appointments),
            'conflicts': conflicts if conflicts else None,
            'series_id': series_id
        }

    def _normalize_datetime_timezone(self, dt1: datetime, dt2: datetime) -> tuple[datetime, datetime]:
        """Normalize two datetime objects to have the same timezone info"""
        if dt1.tzinfo is not None and dt2.tzinfo is None:
            # Make dt2 timezone-aware like dt1
            dt2 = dt2.replace(tzinfo=dt1.tzinfo)
        elif dt1.tzinfo is None and dt2.tzinfo is not None:
            # Make both timezone-naive
            dt2 = dt2.replace(tzinfo=None)
        return dt1, dt2

    def _generate_recurring_dates(self, start_date: datetime, config) -> List[datetime]:
        """Generate list of dates for recurring appointments"""
        
        dates = []
        current_date = start_date
        
        # Always include the start date
        dates.append(current_date)
        
        # Calculate end date - ensure timezone consistency
        if config.end_type == 'date' and config.end_date:
            end_date = config.end_date
            # Normalize timezone info between start_date and end_date
            start_date, end_date = self._normalize_datetime_timezone(start_date, end_date)
        else:
            # Default to 1 year if no end date specified
            end_date = start_date + timedelta(days=365)
        
        count = 1  # Start with 1 since we already added start_date
        max_count = config.max_occurrences if config.end_type == 'occurrences' else 100
        
        if config.frequency == 'weekly':
            # For weekly, add appointments based on selected days of week
            current_date = start_date + timedelta(weeks=config.interval)
            
            while count < max_count and current_date <= end_date:
                # Find the start of current week (Monday)
                week_start = current_date - timedelta(days=current_date.weekday())
                
                # Check each day of the week
                for day_offset in range(7):
                    day_date = week_start + timedelta(days=day_offset)
                    day_of_week = day_date.weekday()  # 0=Monday, 6=Sunday
                    
                    # Convert to our format (0=Sunday, 1=Monday, etc.)
                    day_of_week_converted = (day_of_week + 1) % 7
                    
                    if (day_of_week_converted in config.days_of_week and 
                        day_date >= current_date and 
                        day_date <= end_date):
                        # Set the time to match the original appointment
                        appointment_datetime = day_date.replace(
                            hour=start_date.hour,
                            minute=start_date.minute,
                            second=start_date.second,
                            microsecond=start_date.microsecond
                        )
                        dates.append(appointment_datetime)
                        count += 1
                        
                        if count >= max_count:
                            break
                
                current_date += timedelta(weeks=config.interval)
                
        elif config.frequency == 'monthly':
            # For monthly, add appointments on same day of month
            current_date = start_date
            for _ in range(max_count - 1):  # -1 because we already added start_date
                try:
                    # Add months
                    if current_date.month + config.interval > 12:
                        next_year = current_date.year + ((current_date.month + config.interval - 1) // 12)
                        next_month = ((current_date.month + config.interval - 1) % 12) + 1
                    else:
                        next_year = current_date.year
                        next_month = current_date.month + config.interval
                    
                    current_date = current_date.replace(year=next_year, month=next_month)
                    
                    if current_date <= end_date:
                        dates.append(current_date)
                    else:
                        break
                except ValueError:
                    # Handle edge cases like Feb 31 -> Feb 28/29
                    break
        
        return dates

    def get_appointment(self, appointment_id: int) -> Optional[Appointment]:
        """Get appointment by ID with related data"""
        return self.db.query(Appointment).options(
            joinedload(Appointment.student),
            joinedload(Appointment.teacher),
            joinedload(Appointment.school)
        ).filter(Appointment.id == appointment_id).first()

    def update_appointment(self, appointment_id: int, appointment_data: AppointmentUpdate) -> Optional[Appointment]:
        """Update an existing appointment and its linked therapy session, goals, and objectives"""
        from app.models.therapy_session import TherapySession
        from app.models.session_goal import SessionGoal
        from app.models.session_objective import SessionObjective
        
        # Get the existing appointment
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None
        
        # Extract goal/objective planning data
        planned_goals = appointment_data.planned_goals
        planned_objectives = appointment_data.planned_objectives
        
        print(f"🔄 Update appointment {appointment_id} - planned_goals: {planned_goals}")
        print(f"🔄 Update appointment {appointment_id} - planned_objectives: {planned_objectives}")
        
        # Update appointment fields (exclude the planning fields)
        update_dict = appointment_data.dict(exclude={'planned_goals', 'planned_objectives'}, exclude_unset=True)
        for field, value in update_dict.items():
            setattr(appointment, field, value)
        
        appointment.modified_date = datetime.now()
        self.db.flush()  # Flush to ensure appointment changes are saved
        
        # Get or create therapy session
        therapy_session = self.db.query(TherapySession).filter(
            TherapySession.appointment_id == appointment.id
        ).first()
        
        if not therapy_session:
            # Create therapy session if it doesn't exist (shouldn't happen, but safety check)
            therapy_session = TherapySession(
                student_id=appointment.student_id,
                appointment_id=appointment.id,
                session_date=appointment.start_datetime,
                start_time=appointment.start_datetime,
                end_time=appointment.end_datetime,
                planned_duration_minutes=int((appointment.end_datetime - appointment.start_datetime).total_seconds() / 60),
                session_type='individual',
                status='planned',
                created_from='appointment',
                goals_addressed=True if (planned_goals or planned_objectives) else False
            )
            self.db.add(therapy_session)
            self.db.flush()
        else:
            # Update therapy session timing if appointment times changed
            therapy_session.session_date = appointment.start_datetime
            therapy_session.start_time = appointment.start_datetime
            therapy_session.end_time = appointment.end_datetime
            therapy_session.planned_duration_minutes = int((appointment.end_datetime - appointment.start_datetime).total_seconds() / 60)
            therapy_session.goals_addressed = True if (planned_goals or planned_objectives) else False
        
        # Update session goals
        if planned_goals is not None:
            # Remove existing session goals
            self.db.query(SessionGoal).filter(
                SessionGoal.therapy_session_id == therapy_session.id
            ).delete(synchronize_session=False)
            
            # Add new session goals
            for planned_goal in planned_goals:
                session_goal = SessionGoal(
                    therapy_session_id=therapy_session.id,
                    goal_id=planned_goal.goal_id,
                    planned=planned_goal.planned,
                    worked_on=planned_goal.worked_on,
                    priority=planned_goal.priority
                )
                self.db.add(session_goal)
        
        # Update session objectives
        if planned_objectives is not None:
            # Remove existing session objectives
            self.db.query(SessionObjective).filter(
                SessionObjective.therapy_session_id == therapy_session.id
            ).delete(synchronize_session=False)
            
            # Add new session objectives
            for planned_objective in planned_objectives:
                session_objective = SessionObjective(
                    therapy_session_id=therapy_session.id,
                    objective_id=planned_objective.objective_id,
                    goal_id=planned_objective.goal_id,
                    planned=planned_objective.planned,
                    worked_on=planned_objective.worked_on,
                    priority=planned_objective.priority,
                    pre_session_notes=planned_objective.pre_session_notes
                )
                self.db.add(session_objective)
        
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def delete_appointment(self, appointment_id: int) -> bool:
        """Delete an appointment and its associated therapy session, goals, and objectives"""
        from app.models.therapy_session import TherapySession
        from app.models.session_goal import SessionGoal
        from app.models.session_objective import SessionObjective
        
        appointment = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False
        
        print(f"🗑️ Deleting appointment {appointment_id} and associated therapy data")
        
        # Get the associated therapy session
        therapy_session = self.db.query(TherapySession).filter(
            TherapySession.appointment_id == appointment_id
        ).first()
        
        if therapy_session:
            # Delete session goals and objectives first (foreign key constraints)
            deleted_goals = self.db.query(SessionGoal).filter(
                SessionGoal.therapy_session_id == therapy_session.id
            ).delete(synchronize_session=False)
            
            deleted_objectives = self.db.query(SessionObjective).filter(
                SessionObjective.therapy_session_id == therapy_session.id
            ).delete(synchronize_session=False)
            
            print(f"🗑️ Deleted {deleted_goals} session goals and {deleted_objectives} session objectives")
            
            # Delete the therapy session
            self.db.delete(therapy_session)
            print(f"🗑️ Deleted therapy session {therapy_session.id}")
        
        # Delete the appointment
        self.db.delete(appointment)
        self.db.commit()
        
        print(f"✅ Successfully deleted appointment {appointment_id}")
        return True

    def get_appointments_by_date_range(
        self,
        start_date: date,
        end_date: date,
        student_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        school_id: Optional[int] = None,
        appointment_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Appointment]:
        """Get appointments within a date range with optional filters"""
        query = self.db.query(Appointment).options(
            joinedload(Appointment.student),
            joinedload(Appointment.teacher),
            joinedload(Appointment.school)
        )

        # Date range filter
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(
            and_(
                Appointment.start_datetime >= start_datetime,
                Appointment.start_datetime <= end_datetime
            )
        )

        # Optional filters
        if student_id:
            query = query.filter(Appointment.student_id == student_id)
        if teacher_id:
            query = query.filter(Appointment.teacher_id == teacher_id)
        if school_id:
            query = query.filter(Appointment.school_id == school_id)
        if appointment_type:
            query = query.filter(Appointment.appointment_type == appointment_type)
        if status:
            query = query.filter(Appointment.status == status)

        return query.order_by(Appointment.start_datetime).all()

    def get_student_appointments(
        self,
        student_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Appointment]:
        """Get all appointments for a specific student"""
        query = self.db.query(Appointment).options(
            joinedload(Appointment.teacher),
            joinedload(Appointment.school)
        ).filter(Appointment.student_id == student_id)

        if start_date and end_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(
                and_(
                    Appointment.start_datetime >= start_datetime,
                    Appointment.start_datetime <= end_datetime
                )
            )

        return query.order_by(Appointment.start_datetime).all()

    def get_teacher_appointments(
        self,
        teacher_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Appointment]:
        """Get all appointments for a specific teacher"""
        query = self.db.query(Appointment).options(
            joinedload(Appointment.student),
            joinedload(Appointment.school)
        ).filter(Appointment.teacher_id == teacher_id)

        if start_date and end_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(
                and_(
                    Appointment.start_datetime >= start_datetime,
                    Appointment.start_datetime <= end_datetime
                )
            )

        return query.order_by(Appointment.start_datetime).all()

    def check_time_conflict(
        self,
        student_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        exclude_appointment_id: Optional[int] = None
    ) -> bool:
        """Check if student has conflicting appointments in the time slot"""
        query = self.db.query(Appointment).filter(
            and_(
                Appointment.student_id == student_id,
                Appointment.status.in_(['scheduled', 'in_progress']),
                or_(
                    # New appointment starts during existing appointment
                    and_(
                        Appointment.start_datetime <= start_datetime,
                        Appointment.end_datetime > start_datetime
                    ),
                    # New appointment ends during existing appointment
                    and_(
                        Appointment.start_datetime < end_datetime,
                        Appointment.end_datetime >= end_datetime
                    ),
                    # New appointment completely contains existing appointment
                    and_(
                        Appointment.start_datetime >= start_datetime,
                        Appointment.end_datetime <= end_datetime
                    )
                )
            )
        )

        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)

        return query.first() is not None

    def get_available_time_slots(
        self,
        student_id: int,
        target_date: date,
        duration_minutes: int = 30,
        start_hour: int = 8,
        end_hour: int = 17
    ) -> List[datetime]:
        """Get available time slots for a student on a given date"""
        # Get all appointments for the student on the target date
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        existing_appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.student_id == student_id,
                Appointment.status.in_(['scheduled', 'in_progress']),
                Appointment.start_datetime >= start_datetime,
                Appointment.start_datetime <= end_datetime
            )
        ).order_by(Appointment.start_datetime).all()

        # Generate potential time slots
        available_slots = []
        current_time = datetime.combine(target_date, datetime.min.time().replace(hour=start_hour))
        end_time = datetime.combine(target_date, datetime.min.time().replace(hour=end_hour))

        while current_time < end_time:
            slot_end = current_time.replace(minute=current_time.minute + duration_minutes)
            
            # Check if this slot conflicts with any existing appointment
            conflict = False
            for appointment in existing_appointments:
                if (current_time < appointment.end_datetime and 
                    slot_end > appointment.start_datetime):
                    conflict = True
                    break
            
            if not conflict:
                available_slots.append(current_time)
            
            # Move to next 5-minute increment
            current_time = current_time.replace(minute=current_time.minute + 5)

        return available_slots

    def get_appointments_by_series(self, series_id: str) -> List[Appointment]:
        """Get all appointments that belong to a specific series"""
        return self.db.query(Appointment).filter(
            Appointment.series_id == series_id
        ).order_by(Appointment.start_datetime).all()

    def delete_appointment_series(self, series_id: str) -> bool:
        """Delete all appointments and associated therapy sessions in a series"""
        from app.models.therapy_session import TherapySession
        
        # Get all appointments in the series
        appointments = self.get_appointments_by_series(series_id)
        if not appointments:
            return False
        
        # Delete associated therapy sessions first (cascade should handle this, but being explicit)
        therapy_sessions = self.db.query(TherapySession).filter(
            TherapySession.series_id == series_id
        ).all()
        
        for session in therapy_sessions:
            self.db.delete(session)
        
        # Delete all appointments in the series
        for appointment in appointments:
            self.db.delete(appointment)
        
        self.db.commit()
        return True

    def update_appointment_series(self, series_id: str, appointment_data: AppointmentUpdate) -> List[Appointment]:
        """Update all appointments in a series with the provided data"""
        from app.models.therapy_session import TherapySession
        
        # Get all appointments in the series
        appointments = self.get_appointments_by_series(series_id)
        if not appointments:
            return []
        
        updated_appointments = []
        
        for appointment in appointments:
            # Calculate time offset for this appointment if we're updating times
            time_offset = None
            if appointment_data.start_datetime or appointment_data.end_datetime:
                # For series updates, we'll maintain the relative time differences
                # This is a simplified approach - you might want more sophisticated logic
                first_appointment = appointments[0]
                time_offset = appointment.start_datetime - first_appointment.start_datetime
            
            # Update appointment fields
            update_data = appointment_data.dict(exclude_unset=True)
            
            # Handle time updates with offset
            if appointment_data.start_datetime and time_offset is not None:
                new_start = appointment_data.start_datetime + time_offset
                new_end = appointment_data.end_datetime + time_offset if appointment_data.end_datetime else None
                update_data['start_datetime'] = new_start
                if new_end:
                    update_data['end_datetime'] = new_end
            
            # Apply updates
            for field, value in update_data.items():
                if hasattr(appointment, field):
                    setattr(appointment, field, value)
            
            # Update associated therapy session if it exists
            if appointment.therapy_session:
                therapy_session = appointment.therapy_session
                if 'start_datetime' in update_data:
                    therapy_session.session_date = update_data['start_datetime']
                    therapy_session.start_time = update_data['start_datetime']
                if 'end_datetime' in update_data:
                    therapy_session.end_time = update_data['end_datetime']
                if 'notes' in update_data:
                    therapy_session.prep_notes = update_data['notes']
            
            updated_appointments.append(appointment)
        
        self.db.commit()
        
        # Refresh all updated appointments
        for appointment in updated_appointments:
            self.db.refresh(appointment)
        
        return updated_appointments


