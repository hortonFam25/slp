import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.time_block_activity import TimeBlockActivity
from app.models.activity_student_assignment import ActivityStudentAssignment
from app.models.time_block import TimeBlock
from app.schemas.time_block import TimeBlockActivityCreate, TimeBlockActivityUpdate

logger = logging.getLogger(__name__)


class TimeBlockActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_activity(self, activity_data: TimeBlockActivityCreate) -> TimeBlockActivity:
        """Create a new time block activity with validation and student assignments"""
        from datetime import datetime
        
        # Extract student assignments before creating activity
        assigned_student_ids = activity_data.assigned_student_ids or []
        activity_dict = activity_data.dict(exclude={'assigned_student_ids'})
        
        # Create the activity
        activity = TimeBlockActivity(**activity_dict)
        
        # Validate time constraints
        validation = activity.validate_time_within_block()
        if not validation["valid"]:
            raise ValueError(validation["error"])
        
        # Always sync datetime fields to ensure they're set
        if activity.start_datetime and activity.end_datetime:
            activity.sync_minutes_with_datetime()
        else:
            # Force sync from minutes to datetime
            activity.sync_datetime_with_minutes()
        
        self.db.add(activity)
        self.db.flush()  # Get activity ID
        
        # Create student assignments
        for student_id in assigned_student_ids:
            assignment = ActivityStudentAssignment(
                activity_id=activity.id,
                student_id=student_id,
                status='assigned',
                created_date=datetime.now(),
                modified_date=datetime.now()
            )
            self.db.add(assignment)
        
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def get_activity(self, activity_id: int) -> Optional[TimeBlockActivity]:
        """Get a specific time block activity by ID"""
        return self.db.query(TimeBlockActivity).filter(
            TimeBlockActivity.id == activity_id
        ).first()

    def get_activities_by_time_block(self, time_block_id: int) -> List[TimeBlockActivity]:
        """Get all activities for a specific time block, ordered by sequence"""
        from sqlalchemy.orm import joinedload
        return self.db.query(TimeBlockActivity).options(
            joinedload(TimeBlockActivity.student_assignments).joinedload(ActivityStudentAssignment.student)
        ).filter(
            TimeBlockActivity.time_block_id == time_block_id
        ).order_by(TimeBlockActivity.sequence_order).all()

    def update_activity(self, activity_id: int, activity_data: TimeBlockActivityUpdate) -> Optional[TimeBlockActivity]:
        """Update an existing time block activity"""
        activity = self.get_activity(activity_id)
        if not activity:
            return None

        # Update fields that are provided
        update_data = activity_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(activity, field, value)

        self.db.commit()
        self.db.refresh(activity)
        return activity

    def delete_activity(self, activity_id: int) -> bool:
        """Delete a time block activity"""
        activity = self.get_activity(activity_id)
        if not activity:
            return False

        self.db.delete(activity)
        self.db.commit()
        return True

    def assign_student_to_activity(self, activity_id: int, student_id: int) -> bool:
        """Assign a student to an activity"""
        from datetime import datetime
        
        # Check if assignment already exists
        existing = self.db.query(ActivityStudentAssignment).filter(
            and_(
                ActivityStudentAssignment.activity_id == activity_id,
                ActivityStudentAssignment.student_id == student_id
            )
        ).first()
        
        if existing:
            if existing.status != 'assigned':
                existing.status = 'assigned'
                existing.modified_date = datetime.now()
                self.db.commit()
            return True
        
        # Create new assignment
        assignment = ActivityStudentAssignment(
            activity_id=activity_id,
            student_id=student_id,
            status='assigned',
            created_date=datetime.now(),
            modified_date=datetime.now()
        )
        self.db.add(assignment)
        self.db.commit()
        return True

    def remove_student_from_activity(self, activity_id: int, student_id: int) -> bool:
        """Remove a student from an activity"""
        assignment = self.db.query(ActivityStudentAssignment).filter(
            and_(
                ActivityStudentAssignment.activity_id == activity_id,
                ActivityStudentAssignment.student_id == student_id
            )
        ).first()
        
        if assignment:
            self.db.delete(assignment)
            self.db.commit()
            return True
        return False

    def update_activity_series(self, series_id: str, activity_updates: List[dict]) -> dict:
        """Update activities across all time blocks in a series"""
        from app.models.appointment import Appointment
        from datetime import datetime
        
        # Get all time blocks in this series by finding appointments with this series_id
        appointments = self.db.query(Appointment).filter(
            and_(
                Appointment.series_id == series_id,
                Appointment.time_block_id.isnot(None)
            )
        ).all()
        
        logger.debug("Found %d appointments with series_id %s", len(appointments), series_id)
        
        time_block_ids = list(set([apt.time_block_id for apt in appointments if apt.time_block_id]))
        logger.debug("Unique time block IDs in series: %s", time_block_ids)
        
        if not time_block_ids:
            return {"success": False, "message": "No time blocks found for this series"}
        
        updated_activities = []
        
        # Update activities in each time block
        for time_block_id in time_block_ids:
            try:
                activities = self.get_activities_by_time_block(time_block_id)
                logger.debug("Time block %s has %d activities", time_block_id, len(activities))
                
                # If this time block has no activities but we're trying to update activities,
                # create the activities for this time block first
                if len(activities) == 0 and len(activity_updates) > 0:
                    logger.debug("Creating missing activities for time block %s", time_block_id)
                    for activity_update in activity_updates:
                        # Create new activity for this time block
                        new_activity = TimeBlockActivity(
                            time_block_id=time_block_id,
                            start_minute=activity_update.get('start_minute', 0),
                            duration_minutes=activity_update.get('duration_minutes', 5),
                            activity_name=activity_update.get('activity_name', ''),
                            activity_type=activity_update.get('activity_type'),
                            description=activity_update.get('description'),
                            materials_needed=activity_update.get('materials_needed'),
                            notes=activity_update.get('notes'),
                            sequence_order=activity_update.get('sequence_order', 1)
                        )
                    
                        self.db.add(new_activity)
                        self.db.flush()
                        self.db.refresh(new_activity)
                        
                        # Sync datetime fields
                        new_activity.sync_datetime_with_minutes()
                        
                        # Create student assignments
                        assigned_student_ids = activity_update.get('assigned_student_ids', [])
                        for student_id in assigned_student_ids:
                            assignment = ActivityStudentAssignment(
                                activity_id=new_activity.id,
                                student_id=student_id,
                                status='assigned',
                                created_date=datetime.now(),
                                modified_date=datetime.now()
                            )
                            self.db.add(assignment)
                        
                        updated_activities.append(new_activity)
                        logger.debug(
                            "Created activity %r with %d students",
                            new_activity.activity_name,
                            len(assigned_student_ids),
                        )
                    
                    # Skip to next time block since we just created all activities
                    continue
                
                for activity_update in activity_updates:
                    # Find matching activity by sequence_order or activity_name
                    target_activity = None
                    if 'sequence_order' in activity_update:
                        target_activity = next((act for act in activities if act.sequence_order == activity_update['sequence_order']), None)
                    elif 'activity_name' in activity_update:
                        target_activity = next((act for act in activities if act.activity_name == activity_update['activity_name']), None)
                
                    if target_activity:
                        logger.debug(
                            "Updating activity %r in time block %s",
                            target_activity.activity_name,
                            time_block_id,
                        )
                        
                        # Update the activity fields (exclude read-only, datetime, and relationship fields)
                        excluded_fields = ['id', 'time_block_id', 'created_date', 'modified_date', 'start_datetime', 'end_datetime', 'assigned_students', 'student_assignments']
                        for field, value in activity_update.items():
                            if hasattr(target_activity, field) and field not in excluded_fields:
                                old_value = getattr(target_activity, field)
                                setattr(target_activity, field, value)
                                logger.debug("  %s: %s to %s", field, old_value, value)
                        
                        # Refresh to ensure time_block relationship is loaded
                        self.db.flush()
                        self.db.refresh(target_activity)
                        
                        # Always sync datetime fields after any update to ensure consistency
                        target_activity.sync_datetime_with_minutes()
                        logger.debug(
                            "Synced minutes to datetime: %s - %s",
                            target_activity.start_datetime,
                            target_activity.end_datetime,
                        )
                        
                        # Update student assignments if provided
                        if 'assigned_student_ids' in activity_update:
                            # Clear existing assignments
                            for assignment in target_activity.student_assignments:
                                self.db.delete(assignment)
                            
                            # Create new assignments
                            new_student_ids = activity_update['assigned_student_ids'] or []
                            for student_id in new_student_ids:
                                assignment = ActivityStudentAssignment(
                                    activity_id=target_activity.id,
                                    student_id=student_id,
                                    status='assigned',
                                    created_date=datetime.now(),
                                    modified_date=datetime.now()
                                )
                                self.db.add(assignment)
                            
                            logger.debug("Updated student assignments: %d students", len(new_student_ids))
                        
                        updated_activities.append(target_activity)
                    
            except Exception as e:
                logger.exception("Error processing time block %s", time_block_id)
                # Rollback the session to clear the error state
                self.db.rollback()
                # Continue with other time blocks even if one fails
                continue
        
        self.db.commit()
        
        return {
            "success": True,
            "message": f"Updated {len(updated_activities)} activities across {len(time_block_ids)} time blocks",
            "updated_activities": len(updated_activities),
            "updated_time_blocks": len(time_block_ids)
        }

    def reorder_activities(self, time_block_id: int, activity_order: List[int]) -> List[TimeBlockActivity]:
        """Reorder activities for a time block"""
        activities = self.get_activities_by_time_block(time_block_id)
        
        # Create a mapping of activity_id to new order
        order_map = {activity_id: index + 1 for index, activity_id in enumerate(activity_order)}
        
        # Update sequence_order for each activity
        for activity in activities:
            if activity.id in order_map:
                activity.sequence_order = order_map[activity.id]
        
        self.db.commit()
        
        # Return reordered activities
        return self.get_activities_by_time_block(time_block_id)

    def check_time_overlap(self, time_block_id: int, start_minute: int, duration_minutes: int, exclude_activity_id: Optional[int] = None) -> bool:
        """Check if an activity time overlaps with existing activities"""
        end_minute = start_minute + duration_minutes
        
        query = self.db.query(TimeBlockActivity).filter(
            and_(
                TimeBlockActivity.time_block_id == time_block_id,
                # Check for overlap: new activity starts before existing ends AND new activity ends after existing starts
                TimeBlockActivity.start_minute < end_minute,
                (TimeBlockActivity.start_minute + TimeBlockActivity.duration_minutes) > start_minute
            )
        )
        
        if exclude_activity_id:
            query = query.filter(TimeBlockActivity.id != exclude_activity_id)
        
        return query.first() is not None

    def get_next_sequence_order(self, time_block_id: int) -> int:
        """Get the next sequence order for a new activity"""
        max_order = self.db.query(TimeBlockActivity.sequence_order).filter(
            TimeBlockActivity.time_block_id == time_block_id
        ).order_by(TimeBlockActivity.sequence_order.desc()).first()
        
        return (max_order[0] + 1) if max_order and max_order[0] else 1

    def get_available_time_slots(self, time_block_id: int, duration_minutes: int = 5) -> List[dict]:
        """Get available time slots for new activities"""
        from app.models.time_block import TimeBlock
        
        # Get the time block to know total duration
        time_block = self.db.query(TimeBlock).filter(TimeBlock.id == time_block_id).first()
        if not time_block:
            return []
        
        total_duration = time_block.duration_minutes
        activities = self.get_activities_by_time_block(time_block_id)
        
        # Create a list of occupied minutes
        occupied_minutes = set()
        for activity in activities:
            for minute in range(activity.start_minute, activity.start_minute + activity.duration_minutes):
                occupied_minutes.add(minute)
        
        # Find available slots
        available_slots = []
        current_start = 0
        
        while current_start + duration_minutes <= total_duration:
            # Check if this slot is available
            slot_minutes = set(range(current_start, current_start + duration_minutes))
            if not slot_minutes.intersection(occupied_minutes):
                available_slots.append({
                    "start_minute": current_start,
                    "end_minute": current_start + duration_minutes,
                    "duration_minutes": duration_minutes
                })
            current_start += 5  # Move in 5-minute increments
        
        return available_slots
