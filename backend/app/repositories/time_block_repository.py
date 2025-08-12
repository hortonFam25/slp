from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from app.models.time_block import TimeBlock
from app.models.block_assignment import BlockAssignment
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.school import School
from app.schemas.time_block import TimeBlockCreate, TimeBlockUpdate


class TimeBlockRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_time_block(self, time_block_data: TimeBlockCreate) -> TimeBlock:
        """Create a new time block"""
        time_block = TimeBlock(**time_block_data.dict())
        self.db.add(time_block)
        self.db.commit()
        self.db.refresh(time_block)
        return time_block

    def get_time_block(self, time_block_id: int) -> Optional[TimeBlock]:
        """Get time block by ID with related data"""
        return self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        ).filter(TimeBlock.id == time_block_id).first()

    def update_time_block(self, time_block_id: int, time_block_data: TimeBlockUpdate) -> Optional[TimeBlock]:
        """Update a time block"""
        time_block = self.db.query(TimeBlock).filter(TimeBlock.id == time_block_id).first()
        if time_block:
            update_data = time_block_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(time_block, field, value)
            time_block.modified_date = datetime.now()
            self.db.commit()
            self.db.refresh(time_block)
        return time_block

    def delete_time_block(self, time_block_id: int) -> bool:
        """Delete a time block and all associated appointments, therapy sessions, goals, and objectives"""
        from app.models.appointment import Appointment
        from app.models.therapy_session import TherapySession
        from app.models.session_goal import SessionGoal
        from app.models.session_objective import SessionObjective
        from app.repositories.appointment_repository import AppointmentRepository
        
        time_block = self.db.query(TimeBlock).filter(TimeBlock.id == time_block_id).first()
        if not time_block:
            return False
        
        print(f"🗑️ Deleting time block {time_block_id} and all associated appointments")
        
        # Get all appointments associated with this time block
        appointments = self.db.query(Appointment).filter(
            Appointment.time_block_id == time_block_id
        ).all()
        
        if appointments:
            print(f"🗑️ Found {len(appointments)} appointments to delete")
            
            # Use the appointment repository to properly delete each appointment
            # This ensures therapy sessions, goals, and objectives are also deleted
            appointment_repo = AppointmentRepository(self.db)
            for appointment in appointments:
                # We need to handle this manually since we're already in a transaction
                therapy_session = self.db.query(TherapySession).filter(
                    TherapySession.appointment_id == appointment.id
                ).first()
                
                if therapy_session:
                    # Delete session goals and objectives
                    self.db.query(SessionGoal).filter(
                        SessionGoal.therapy_session_id == therapy_session.id
                    ).delete(synchronize_session=False)
                    
                    self.db.query(SessionObjective).filter(
                        SessionObjective.therapy_session_id == therapy_session.id
                    ).delete(synchronize_session=False)
                    
                    # Delete therapy session
                    self.db.delete(therapy_session)
                
                # Delete appointment
                self.db.delete(appointment)
            
            print(f"🗑️ Deleted {len(appointments)} appointments and their therapy data")
        
        # Delete the time block (block assignments and activities should cascade due to foreign key constraints)
        self.db.delete(time_block)
        self.db.commit()
        
        print(f"✅ Successfully deleted time block {time_block_id}")
        return True

    def get_time_blocks_by_date_range(
        self,
        start_date: date,
        end_date: date,
        teacher_id: Optional[int] = None,
        school_id: Optional[int] = None,
        block_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[TimeBlock]:
        """Get time blocks within a date range with optional filters"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        )

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
        end_date: Optional[date] = None
    ) -> List[TimeBlock]:
        """Get all time blocks for a specific teacher"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        ).filter(TimeBlock.teacher_id == teacher_id)

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
        block_type: Optional[str] = None
    ) -> List[TimeBlock]:
        """Get time blocks that have available spots"""
        query = self.db.query(TimeBlock).options(
            joinedload(TimeBlock.teacher),
            joinedload(TimeBlock.school),
            joinedload(TimeBlock.block_assignments).joinedload(BlockAssignment.student)
        )

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
        """Check if teacher has conflicting time blocks in the time slot"""
        query = self.db.query(TimeBlock).filter(
            and_(
                TimeBlock.teacher_id == teacher_id,
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

    def get_block_students(self, time_block_id: int) -> List[Student]:
        """Get all students assigned to a time block"""
        assignments = self.db.query(BlockAssignment).options(
            joinedload(BlockAssignment.student)
        ).filter(
            and_(
                BlockAssignment.time_block_id == time_block_id,
                BlockAssignment.status == 'assigned'
            )
        ).all()

        return [assignment.student for assignment in assignments]
