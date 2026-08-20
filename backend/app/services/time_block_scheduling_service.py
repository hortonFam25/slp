import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import uuid4

from app.models.time_block import TimeBlock
from app.models.appointment import Appointment
from app.models.therapy_session import TherapySession
from app.models.session_goal import SessionGoal
from app.models.session_objective import SessionObjective
from app.models.block_assignment import BlockAssignment
from app.models.goal_objective import GoalObjective
from app.repositories.appointment_repository import AppointmentRepository
from app.schemas.appointment import AppointmentCreate, PlannedGoal, PlannedObjective

logger = logging.getLogger(__name__)


class TimeBlockSchedulingService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)

    def schedule_time_block(
        self, 
        time_block_id: int, 
        recurring_config: Optional[Dict[str, Any]] = None,
        student_goal_assignments: Optional[Dict[int, Dict[str, List[int]]]] = None
    ) -> Dict[str, Any]:
        """
        Schedule a time block by creating individual appointments for all assigned students.
        
        Args:
            time_block_id: ID of the time block to schedule
            recurring_config: Optional recurring schedule configuration
            student_goal_assignments: Optional dict mapping student_id to {goals: [goal_ids], objectives: [objective_ids]}
        
        Returns:
            Dict with created appointments, conflicts, and summary
        """
        logger.debug(
            "Received student_goal_assignments (%s): %s",
            type(student_goal_assignments).__name__,
            student_goal_assignments,
        )
        if student_goal_assignments:
            for student_id, assignments in student_goal_assignments.items():
                logger.debug("  Student %s: %s", student_id, assignments)
        # Get the time block with assignments
        time_block = self.db.query(TimeBlock).filter(
            TimeBlock.id == time_block_id
        ).first()
        
        if not time_block:
            raise ValueError(f"Time block {time_block_id} not found")
        
        # Get active student assignments
        active_assignments = [
            assignment for assignment in time_block.block_assignments 
            if assignment.status == 'assigned'
        ]
        
        if not active_assignments:
            return {
                "appointments_created": [],
                "conflicts": [],
                "message": "No students assigned to time block"
            }
        
        # Generate series ID for linking appointments
        series_id = str(uuid4())
        
        # Determine dates to schedule
        schedule_dates = self._calculate_schedule_dates(time_block, recurring_config)
        
        created_appointments = []
        conflicts = []
        
        for schedule_date in schedule_dates:
            # Calculate appointment times for this date
            appointment_start = self._combine_date_and_time(schedule_date, time_block.start_datetime.time())
            appointment_end = self._combine_date_and_time(schedule_date, time_block.end_datetime.time())
            
            # Create appointments for each assigned student
            for assignment in active_assignments:
                student_id = assignment.student_id
                
                # Check for conflicts
                if self.appointment_repo.check_time_conflict(
                    student_id=student_id,
                    start_datetime=appointment_start,
                    end_datetime=appointment_end
                ):
                    conflicts.append({
                        "student_id": student_id,
                        "student_name": f"{assignment.student.first} {assignment.student.last}",
                        "conflict_time": appointment_start.strftime('%Y-%m-%d %H:%M'),
                        "reason": "Student has conflicting appointment"
                    })
                    continue
                
                # Get goal/objective assignments for this student
                planned_goals = []
                planned_objectives = []
                # Convert student_id to string to match JSON key format
                student_id_str = str(student_id)
                if student_goal_assignments and student_id_str in student_goal_assignments:
                    goal_ids = student_goal_assignments[student_id_str].get('goals', [])
                    objective_ids = student_goal_assignments[student_id_str].get('objectives', [])
                    
                    logger.debug(
                        "Found goal assignments for student %s: goals=%s, objectives=%s",
                        student_id,
                        goal_ids,
                        objective_ids,
                    )
                    
                    # Convert goal IDs to PlannedGoal objects
                    for goal_id in goal_ids:
                        planned_goals.append(PlannedGoal(
                            goal_id=goal_id,
                            planned=True,
                            worked_on=False,
                            priority=1
                        ))
                    
                    # Convert objective IDs to PlannedObjective objects
                    for objective_id in objective_ids:
                        # Get the goal_id for this objective
                        objective = self.db.query(GoalObjective).filter(GoalObjective.id == objective_id).first()
                        if objective:
                            planned_objectives.append(PlannedObjective(
                                objective_id=objective_id,
                                goal_id=objective.goal_id,
                                planned=True,
                                worked_on=False,
                                priority=1
                            ))
                else:
                    logger.debug(
                        "No goal assignments found for student %s (looking for key %r)",
                        student_id,
                        student_id_str,
                    )
                
                # Create appointment data
                appointment_data = AppointmentCreate(
                    student_id=student_id,
                    teacher_id=time_block.teacher_id,
                    school_id=time_block.school_id,
                    time_block_id=time_block.id,  # Link to time block
                    start_datetime=appointment_start,
                    end_datetime=appointment_end,
                    appointment_type='group',  # Mark as group appointment
                    location=time_block.location,
                    notes=f"Generated from time block: {time_block.title}",
                    series_id=series_id if len(schedule_dates) > 1 else None,
                    planned_goals=planned_goals if planned_goals else None,
                    planned_objectives=planned_objectives if planned_objectives else None
                )
                
                # Create the appointment (this will also create therapy session if goals/objectives are planned)
                # The time_block_id is now included in appointment_data and will be persisted automatically
                appointment = self.appointment_repo.create_appointment(appointment_data)
                
                # Update the therapy session to link to time block and set as group session
                if appointment.therapy_session:
                    appointment.therapy_session.time_block_id = time_block.id
                    appointment.therapy_session.session_type = 'group'
                    # Explicitly mark as dirty for commit
                    self.db.add(appointment.therapy_session)
                
                created_appointments.append({
                    "appointment_id": appointment.id,
                    "student_id": student_id,
                    "student_name": f"{assignment.student.first} {assignment.student.last}",
                    "appointment_time": appointment_start.strftime('%Y-%m-%d %H:%M'),
                    "therapy_session_created": appointment.therapy_session is not None,
                    "goals_planned": len(planned_goals),
                    "objectives_planned": len(planned_objectives)
                })
        
        # Commit all changes
        self.db.commit()
        
        return {
            "appointments_created": created_appointments,
            "conflicts": conflicts,
            "total_appointments": len(created_appointments),
            "total_conflicts": len(conflicts),
            "series_id": series_id if len(schedule_dates) > 1 else None,
            "schedule_dates": [d.strftime('%Y-%m-%d') for d in schedule_dates]
        }
    
    def _calculate_schedule_dates(self, time_block: TimeBlock, recurring_config: Optional[Dict[str, Any]]) -> List[date]:
        """Calculate dates to schedule based on time block and recurring configuration"""
        if not recurring_config:
            # Single occurrence
            return [time_block.start_datetime.date()]
        
        # Handle recurring scheduling
        start_date = recurring_config.get('start_date', time_block.start_datetime.date())
        end_date = recurring_config.get('end_date')
        frequency = recurring_config.get('frequency', 'weekly')
        interval = recurring_config.get('interval', 1)
        days_of_week = recurring_config.get('days_of_week', [time_block.start_datetime.weekday()])
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        dates = []
        current_date = start_date
        
        # Limit to prevent infinite loops
        max_occurrences = recurring_config.get('max_occurrences', 100)
        occurrences_count = 0
        
        while (not end_date or current_date <= end_date) and occurrences_count < max_occurrences:
            if frequency == 'daily':
                if current_date >= start_date:
                    dates.append(current_date)
                    occurrences_count += 1
                current_date += timedelta(days=interval)
            elif frequency == 'weekly':
                if current_date.weekday() in days_of_week and current_date >= start_date:
                    dates.append(current_date)
                    occurrences_count += 1
                current_date += timedelta(days=1)
            else:
                # Default to single occurrence
                if current_date >= start_date:
                    dates.append(current_date)
                break
        
        return dates
    
    def _combine_date_and_time(self, target_date: date, time_obj) -> datetime:
        """Combine a date with a time object to create a datetime"""
        return datetime.combine(target_date, time_obj)
    
    def get_time_block_appointments(self, time_block_id: int) -> List[Appointment]:
        """Get all appointments for a specific time block"""
        return self.db.query(Appointment).filter(
            Appointment.time_block_id == time_block_id
        ).all()
    
    def cancel_time_block_schedule(self, time_block_id: int, cancel_future_only: bool = True) -> Dict[str, Any]:
        """Cancel scheduled appointments for a time block"""
        appointments = self.get_time_block_appointments(time_block_id)
        
        if cancel_future_only:
            now = datetime.now()
            appointments = [apt for apt in appointments if apt.start_datetime > now]
        
        cancelled_count = 0
        for appointment in appointments:
            if appointment.status == 'scheduled':
                appointment.status = 'cancelled'
                if appointment.therapy_session and appointment.therapy_session.status == 'planned':
                    appointment.therapy_session.status = 'cancelled'
                cancelled_count += 1
        
        self.db.commit()
        
        return {
            "cancelled_appointments": cancelled_count,
            "message": f"Cancelled {cancelled_count} appointments for time block"
        }
