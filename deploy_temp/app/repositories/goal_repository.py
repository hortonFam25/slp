from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc, asc
from typing import List, Optional
from datetime import date

from app.models.iep_goal import IEPGoal
from app.models.goal_category import GoalCategory
from app.models.goal_objective import GoalObjective
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.schemas.iep_goal import IEPGoalCreate, IEPGoalUpdate


class GoalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_goal_categories(self) -> List[GoalCategory]:
        """Get all active goal categories"""
        return self.db.query(GoalCategory).filter(GoalCategory.is_active == True).all()

    def get_goals(
        self, 
        student_id: Optional[int] = None,
        goal_status: Optional[str] = None,
        goal_category_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None
    ) -> List[IEPGoal]:
        """Get goals with optional filters"""
        query = self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries)
        )

        if student_id:
            query = query.filter(IEPGoal.student_id == student_id)
        if goal_status:
            query = query.filter(IEPGoal.goal_status == goal_status)
        if goal_category_id:
            query = query.filter(IEPGoal.goal_category_id == goal_category_id)
        if start_date_from:
            query = query.filter(IEPGoal.start_date >= start_date_from)
        if start_date_to:
            query = query.filter(IEPGoal.start_date <= start_date_to)

        return query.order_by(desc(IEPGoal.created_date)).all()

    def get_goal_by_id(self, goal_id: int) -> Optional[IEPGoal]:
        """Get a goal by ID with all related data"""
        return self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries)
        ).filter(IEPGoal.id == goal_id).first()

    def get_goal_with_objectives(self, goal_id: int) -> Optional[IEPGoal]:
        """Get a goal by ID with objectives (alias for get_goal_by_id for compatibility)"""
        return self.get_goal_by_id(goal_id)

    def get_student_goals(self, student_id: int) -> List[IEPGoal]:
        """Get all goals for a specific student"""
        return self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries)
        ).filter(IEPGoal.student_id == student_id).order_by(desc(IEPGoal.created_date)).all()

    def create_goal(self, goal_data: IEPGoalCreate) -> IEPGoal:
        """Create a new IEP goal"""
        goal = IEPGoal(**goal_data.dict())
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update_goal(self, goal_id: int, goal_data: IEPGoalUpdate) -> Optional[IEPGoal]:
        """Update an existing goal"""
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return None

        update_data = goal_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(goal, field, value)

        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete_goal(self, goal_id: int) -> bool:
        """Delete a goal and all related objectives/progress entries"""
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return False

        self.db.delete(goal)
        self.db.commit()
        return True

    def get_goals_by_status(self, status: str) -> List[IEPGoal]:
        """Get all goals with a specific status"""
        return self.db.query(IEPGoal).filter(IEPGoal.goal_status == status).all()

    def get_overdue_goals(self) -> List[IEPGoal]:
        """Get goals that are past their end date"""
        today = date.today()
        return self.db.query(IEPGoal).filter(
            IEPGoal.end_date < today,
            IEPGoal.goal_status == 'Active'
        ).all()


class ObjectiveRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_objectives(
        self,
        goal_id: Optional[int] = None,
        progress_status: Optional[str] = None,
        schedule_frequency: Optional[str] = None
    ) -> List[GoalObjective]:
        """Get objectives with optional filters"""
        query = self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries)
        )

        if goal_id:
            query = query.filter(GoalObjective.goal_id == goal_id)
        if progress_status:
            query = query.filter(GoalObjective.progress_status == progress_status)
        if schedule_frequency:
            query = query.filter(GoalObjective.schedule_frequency == schedule_frequency)

        return query.order_by(asc(GoalObjective.objective_number)).all()

    def get_objective_by_id(self, objective_id: int) -> Optional[GoalObjective]:
        """Get an objective by ID with progress entries"""
        return self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries)
        ).filter(GoalObjective.id == objective_id).first()

    def get_goal_objectives(self, goal_id: int) -> List[GoalObjective]:
        """Get all objectives for a specific goal"""
        return self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries)
        ).filter(GoalObjective.goal_id == goal_id).order_by(asc(GoalObjective.objective_number)).all()

    def create_objective(self, objective_data: dict) -> GoalObjective:
        """Create a new objective"""
        objective = GoalObjective(**objective_data)
        self.db.add(objective)
        self.db.commit()
        self.db.refresh(objective)
        return objective

    def update_objective(self, objective_id: int, objective_data: dict) -> Optional[GoalObjective]:
        """Update an existing objective"""
        objective = self.get_objective_by_id(objective_id)
        if not objective:
            return None

        for field, value in objective_data.items():
            if hasattr(objective, field):
                setattr(objective, field, value)

        self.db.commit()
        self.db.refresh(objective)
        return objective

    def delete_objective(self, objective_id: int) -> bool:
        """Delete an objective and all related progress entries"""
        objective = self.get_objective_by_id(objective_id)
        if not objective:
            return False

        self.db.delete(objective)
        self.db.commit()
        return True


class ProgressEntryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_progress_entries(
        self,
        objective_id: Optional[int] = None,
        progress_date_from: Optional[date] = None,
        progress_date_to: Optional[date] = None,
        therapist_initials: Optional[str] = None
    ) -> List[ObjectiveProgressEntry]:
        """Get progress entries with optional filters"""
        query = self.db.query(ObjectiveProgressEntry).options(
            selectinload(ObjectiveProgressEntry.objective)
        )

        if objective_id:
            query = query.filter(ObjectiveProgressEntry.objective_id == objective_id)
        if progress_date_from:
            query = query.filter(ObjectiveProgressEntry.progress_date >= progress_date_from)
        if progress_date_to:
            query = query.filter(ObjectiveProgressEntry.progress_date <= progress_date_to)
        if therapist_initials:
            query = query.filter(ObjectiveProgressEntry.therapist_initials.ilike(f'%{therapist_initials}%'))

        return query.order_by(desc(ObjectiveProgressEntry.progress_date)).all()

    def get_progress_entry_by_id(self, entry_id: int) -> Optional[ObjectiveProgressEntry]:
        """Get a progress entry by ID"""
        return self.db.query(ObjectiveProgressEntry).filter(ObjectiveProgressEntry.id == entry_id).first()

    def get_objective_progress_entries(self, objective_id: int) -> List[ObjectiveProgressEntry]:
        """Get all progress entries for a specific objective"""
        return self.db.query(ObjectiveProgressEntry).filter(
            ObjectiveProgressEntry.objective_id == objective_id
        ).order_by(desc(ObjectiveProgressEntry.progress_date)).all()

    def create_progress_entry(self, entry_data: dict) -> ObjectiveProgressEntry:
        """Create a new progress entry"""
        entry = ObjectiveProgressEntry(**entry_data)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def update_progress_entry(self, entry_id: int, entry_data: dict) -> Optional[ObjectiveProgressEntry]:
        """Update an existing progress entry"""
        entry = self.get_progress_entry_by_id(entry_id)
        if not entry:
            return None

        for field, value in entry_data.items():
            if hasattr(entry, field):
                setattr(entry, field, value)

        self.db.commit()
        self.db.refresh(entry)
        return entry

    def delete_progress_entry(self, entry_id: int) -> bool:
        """Delete a progress entry"""
        entry = self.get_progress_entry_by_id(entry_id)
        if not entry:
            return False

        self.db.delete(entry)
        self.db.commit()
        return True

    def get_latest_entry_for_objective(self, objective_id: int) -> Optional[ObjectiveProgressEntry]:
        """Get the most recent progress entry for an objective"""
        return self.db.query(ObjectiveProgressEntry).filter(
            ObjectiveProgressEntry.objective_id == objective_id
        ).order_by(desc(ObjectiveProgressEntry.progress_date)).first()
