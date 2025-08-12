from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.time_block_activity import TimeBlockActivity
from app.schemas.time_block import TimeBlockActivityCreate, TimeBlockActivityUpdate


class TimeBlockActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_activity(self, activity_data: TimeBlockActivityCreate) -> TimeBlockActivity:
        """Create a new time block activity"""
        activity = TimeBlockActivity(**activity_data.dict())
        self.db.add(activity)
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
        return self.db.query(TimeBlockActivity).filter(
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
