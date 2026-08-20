"""Goals, objectives and progress entries.

ARCHIVE FILTERING. All three entities in this file are archivable, and they
nest, so filtering has to happen in two places:

1. On the QUERY -- `archived_at IS NULL`, applied to every read path unless the
   caller passes `include_archived=True`.
2. On the EAGER LOADS -- `with_loader_criteria`. These methods return goals with
   their objectives and progress entries attached, and a `selectinload` does not
   inherit the outer query's WHERE clause. Without this, archiving one objective
   would hide it from `GET /api/objectives` and still show it nested inside its
   goal. `with_loader_criteria` is used rather than a filtered relationship
   `primaryjoin` on purpose: those relationships carry `delete-orphan`, and a
   collection that silently loses a member is exactly how delete-orphan destroys
   a row nobody asked to destroy.

`get_*_by_id` returns None for an archived row unless asked otherwise, which is
what turns an archived id into a 404 at the route -- the same answer the caller
used to get after a DELETE.

There is no `delete_*` method any more. Archiving is
`app.services.archive.archive`, and it is reversible.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from app.models.goal_category import GoalCategory
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.schemas.iep_goal import IEPGoalCreate, IEPGoalUpdate


def _active_children(include_archived: bool) -> list:
    """Loader options that keep archived children out of an eager load.

    Applied to whole entities rather than to a named relationship, so a new
    `selectinload` added to a query below is covered without being listed here.
    """
    if include_archived:
        return []
    return [
        with_loader_criteria(GoalObjective, GoalObjective.archived_at.is_(None)),
        with_loader_criteria(
            ObjectiveProgressEntry, ObjectiveProgressEntry.archived_at.is_(None)
        ),
    ]


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
        start_date_to: Optional[date] = None,
        include_archived: bool = False,
    ) -> List[IEPGoal]:
        """Get goals with optional filters"""
        query = self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        )

        if not include_archived:
            query = query.filter(IEPGoal.archived_at.is_(None))
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

    def get_goal_by_id(self, goal_id: int, include_archived: bool = False) -> Optional[IEPGoal]:
        """Get a goal by ID with all related data"""
        query = self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        ).filter(IEPGoal.id == goal_id)
        if not include_archived:
            query = query.filter(IEPGoal.archived_at.is_(None))
        return query.first()

    def get_goal_with_objectives(
        self, goal_id: int, include_archived: bool = False
    ) -> Optional[IEPGoal]:
        """Get a goal by ID with objectives (alias for get_goal_by_id for compatibility)"""
        return self.get_goal_by_id(goal_id, include_archived=include_archived)

    def get_student_goals(self, student_id: int, include_archived: bool = False) -> List[IEPGoal]:
        """Get all goals for a specific student"""
        query = self.db.query(IEPGoal).options(
            selectinload(IEPGoal.goal_category),
            selectinload(IEPGoal.objectives).selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        ).filter(IEPGoal.student_id == student_id)
        if not include_archived:
            query = query.filter(IEPGoal.archived_at.is_(None))
        return query.order_by(desc(IEPGoal.created_date)).all()

    def create_goal(self, goal_data: IEPGoalCreate) -> IEPGoal:
        """Create a new IEP goal"""
        goal = IEPGoal(**goal_data.dict())
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def update_goal(self, goal_id: int, goal_data: IEPGoalUpdate) -> Optional[IEPGoal]:
        """Update an existing goal. An archived goal is not editable -- restore it first."""
        goal = self.get_goal_by_id(goal_id)
        if not goal:
            return None

        update_data = goal_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(goal, field, value)

        self.db.commit()
        self.db.refresh(goal)
        return goal

    def get_goals_by_status(self, status: str, include_archived: bool = False) -> List[IEPGoal]:
        """Get all goals with a specific status"""
        query = self.db.query(IEPGoal).filter(IEPGoal.goal_status == status)
        if not include_archived:
            query = query.filter(IEPGoal.archived_at.is_(None))
        return query.all()

    def get_overdue_goals(self, include_archived: bool = False) -> List[IEPGoal]:
        """Get goals that are past their end date"""
        today = date.today()
        query = self.db.query(IEPGoal).filter(
            IEPGoal.end_date < today,
            IEPGoal.goal_status == 'Active'
        )
        if not include_archived:
            query = query.filter(IEPGoal.archived_at.is_(None))
        return query.all()


class ObjectiveRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_objectives(
        self,
        goal_id: Optional[int] = None,
        progress_status: Optional[str] = None,
        schedule_frequency: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[GoalObjective]:
        """Get objectives with optional filters"""
        query = self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        )

        if not include_archived:
            query = query.filter(GoalObjective.archived_at.is_(None))
        if goal_id:
            query = query.filter(GoalObjective.goal_id == goal_id)
        if progress_status:
            query = query.filter(GoalObjective.progress_status == progress_status)
        if schedule_frequency:
            query = query.filter(GoalObjective.schedule_frequency == schedule_frequency)

        return query.order_by(asc(GoalObjective.objective_number)).all()

    def get_objective_by_id(
        self, objective_id: int, include_archived: bool = False
    ) -> Optional[GoalObjective]:
        """Get an objective by ID with progress entries"""
        query = self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        ).filter(GoalObjective.id == objective_id)
        if not include_archived:
            query = query.filter(GoalObjective.archived_at.is_(None))
        return query.first()

    def get_goal_objectives(
        self, goal_id: int, include_archived: bool = False
    ) -> List[GoalObjective]:
        """Get all objectives for a specific goal"""
        query = self.db.query(GoalObjective).options(
            selectinload(GoalObjective.progress_entries),
            *_active_children(include_archived),
        ).filter(GoalObjective.goal_id == goal_id)
        if not include_archived:
            query = query.filter(GoalObjective.archived_at.is_(None))
        return query.order_by(asc(GoalObjective.objective_number)).all()

    def create_objective(self, objective_data: dict) -> GoalObjective:
        """Create a new objective"""
        objective = GoalObjective(**objective_data)
        self.db.add(objective)
        self.db.commit()
        self.db.refresh(objective)
        return objective

    def update_objective(self, objective_id: int, objective_data: dict) -> Optional[GoalObjective]:
        """Update an existing objective. Archived objectives are not editable."""
        objective = self.get_objective_by_id(objective_id)
        if not objective:
            return None

        for field, value in objective_data.items():
            if hasattr(objective, field):
                setattr(objective, field, value)

        self.db.commit()
        self.db.refresh(objective)
        return objective


class ProgressEntryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_progress_entries(
        self,
        objective_id: Optional[int] = None,
        progress_date_from: Optional[date] = None,
        progress_date_to: Optional[date] = None,
        therapist_initials: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[ObjectiveProgressEntry]:
        """Get progress entries with optional filters"""
        query = self.db.query(ObjectiveProgressEntry).options(
            selectinload(ObjectiveProgressEntry.objective)
        )

        if not include_archived:
            query = query.filter(ObjectiveProgressEntry.archived_at.is_(None))
        if objective_id:
            query = query.filter(ObjectiveProgressEntry.objective_id == objective_id)
        if progress_date_from:
            query = query.filter(ObjectiveProgressEntry.progress_date >= progress_date_from)
        if progress_date_to:
            query = query.filter(ObjectiveProgressEntry.progress_date <= progress_date_to)
        if therapist_initials:
            query = query.filter(ObjectiveProgressEntry.therapist_initials.ilike(f'%{therapist_initials}%'))

        return query.order_by(desc(ObjectiveProgressEntry.progress_date)).all()

    def get_progress_entry_by_id(
        self, entry_id: int, include_archived: bool = False
    ) -> Optional[ObjectiveProgressEntry]:
        """Get a progress entry by ID"""
        query = self.db.query(ObjectiveProgressEntry).filter(
            ObjectiveProgressEntry.id == entry_id
        )
        if not include_archived:
            query = query.filter(ObjectiveProgressEntry.archived_at.is_(None))
        return query.first()

    def get_objective_progress_entries(
        self, objective_id: int, include_archived: bool = False
    ) -> List[ObjectiveProgressEntry]:
        """Get all progress entries for a specific objective"""
        query = self.db.query(ObjectiveProgressEntry).filter(
            ObjectiveProgressEntry.objective_id == objective_id
        )
        if not include_archived:
            query = query.filter(ObjectiveProgressEntry.archived_at.is_(None))
        return query.order_by(desc(ObjectiveProgressEntry.progress_date)).all()

    def create_progress_entry(self, entry_data: dict) -> ObjectiveProgressEntry:
        """Create a new progress entry"""
        entry = ObjectiveProgressEntry(**entry_data)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def update_progress_entry(self, entry_id: int, entry_data: dict) -> Optional[ObjectiveProgressEntry]:
        """Update an existing progress entry. Archived entries are not editable."""
        entry = self.get_progress_entry_by_id(entry_id)
        if not entry:
            return None

        for field, value in entry_data.items():
            if hasattr(entry, field):
                setattr(entry, field, value)

        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_latest_entry_for_objective(
        self, objective_id: int, include_archived: bool = False
    ) -> Optional[ObjectiveProgressEntry]:
        """Get the most recent progress entry for an objective"""
        query = self.db.query(ObjectiveProgressEntry).filter(
            ObjectiveProgressEntry.objective_id == objective_id
        )
        if not include_archived:
            query = query.filter(ObjectiveProgressEntry.archived_at.is_(None))
        return query.order_by(desc(ObjectiveProgressEntry.progress_date)).first()
