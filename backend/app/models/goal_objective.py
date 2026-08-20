from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.archive_event import ArchivableMixin


class GoalObjective(ArchivableMixin, Base):
    __tablename__ = "goal_objectives"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey('iep_goals.id'), nullable=False, index=True)
    objective_number = Column(Integer, nullable=False)
    objective_description = Column(Text, nullable=False)
    progress_status = Column(String(50), nullable=True)
    schedule_frequency = Column(String(50), nullable=True)
    created_date = Column(DateTime, nullable=False, server_default=func.now())
    modified_date = Column(DateTime, nullable=False, server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint('goal_id', 'objective_number', name='uq_goal_objective'),
        CheckConstraint('objective_number >= 1 AND objective_number <= 10', name='ck_objective_number_range'),
    )

    # Relationships
    goal = relationship("IEPGoal", back_populates="objectives")
    progress_entries = relationship("ObjectiveProgressEntry", back_populates="objective", cascade="all, delete-orphan")
    session_objectives = relationship("SessionObjective", back_populates="objective", cascade="all, delete-orphan")

    @property
    def active_progress_entries(self):
        """The progress entries that have not been archived.

        `GoalRepository` attaches `with_loader_criteria` to its eager loads, so
        under a repository read the loaded collection already excludes archived
        entries and this filter is a no-op. It is NOT a no-op under a lazy load
        from `objective.progress_entries` -- which is how every path outside
        `app/repositories/` reaches them -- so the two properties below go
        through here rather than over the raw relationship.
        """
        return [
            entry
            for entry in (self.progress_entries or [])
            if entry.archived_at is None
        ]

    @property
    def latest_progress_entry(self):
        """Get the most recent progress entry for this objective"""
        entries = self.active_progress_entries
        if entries:
            return max(entries, key=lambda x: x.progress_date)
        return None

    @property
    def progress_count(self) -> int:
        """Count of progress entries for this objective"""
        return len(self.active_progress_entries)
