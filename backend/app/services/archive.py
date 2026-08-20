"""Archive and restore, in place of delete.

Every destructive path in this application now lands here. A DELETE route, an
MCP `archive_*` tool and the student Archive button in the React app all call
`archive()`; nothing removes a row of clinical data any more.

WHAT AN ARCHIVE IS
------------------
`archive(db, user_id, entity_type, entity_id)` writes one `archive_events` row
and stamps `archived_at` + `archive_event_id` onto the root and its cascade
set. The stamped rows stay exactly where they were, with every column intact.
They stop being *visible*, because every default query path in
`app/repositories/` filters on `archived_at IS NULL` -- not because anything was
removed.

THE ONE RULE THAT MAKES RESTORE FAITHFUL
----------------------------------------
A cascade stamps ONLY rows that are currently active. A row already archived
under an older event keeps that older event.

Without this, archiving a student in January would re-stamp a goal that was
retired in September, and restoring the student would resurrect that goal --
undoing a decision nobody asked to undo, and leaving no trace that it happened.
With it, restore is exact: `restore(event)` clears the rows whose
`archive_event_id` is that event and no others, so the September goal stays
archived under its September event and comes back only if somebody restores
*that*.

THE CASCADES, AND WHY EACH ONE IS WHAT IT IS
--------------------------------------------
Each cascade mirrors what the DELETE it replaced actually destroyed. That is
the design rule: archiving must hide precisely what deleting used to remove, or
the change is not a like-for-like swap and every caller has to be re-reasoned.

* **student** -> the student, their IEP goals, the objectives under those
  goals, the progress entries under those objectives, their therapy sessions,
  and their appointments.

  NOT `block_assignments`. They are join rows between a student and a group
  time block, they carry no clinical content, and they have no archive columns
  (the migration adds the pair to seven tables; this is not one of them). An
  archived student's assignment row survives untouched and is simply not
  reachable through a default-filtered query, because both the student and any
  appointment the assignment produced are archived. Restoring the student
  brings the group membership back exactly as it was -- which a row-level
  archive of the join would have to reconstruct.

  NOT `time_blocks`. A group block belongs to a therapist and a school, not to
  a student; archiving one student must not hide a block four other children
  still attend.

* **goal** -> the goal, its objectives, and those objectives' progress entries.
  This is what `GoalRepository.delete_goal` destroyed, via the ORM
  `delete-orphan` cascades on `IEPGoal.objectives` and
  `GoalObjective.progress_entries`.

* **objective** -> the objective and its progress entries. Same reasoning.

* **progress_entry** -> itself. It is a leaf.

* **therapy_session** -> itself, and nothing else. Its progress entries belong
  to an OBJECTIVE (`objective_progress_entries.objective_id` is NOT NULL; the
  session link is nullable) and they are the evidence a service was delivered.
  Hiding a session must not blank a child's progress data -- so the entries stay
  active, their `therapy_session_id` still pointing at an archived session.
  This is a DELIBERATE divergence from the old `delete_session`, which took the
  entries with it via `delete-orphan`; nothing was recoverable then, everything
  is now, and the archive framework's job is to stop hiding the record, not to
  reproduce a data-loss bug.

* **appointment** -> itself, plus the therapy session linked to it if that
  session is still active. `Appointment.therapy_session` is a genuine 1:1
  (`uselist=False`), the session exists only because the appointment did, and
  `AppointmentRepository.delete_appointment` deleted the pair. Like-for-like.

* **time_block** -> itself, its appointments and its therapy sessions --
  exactly the set `TimeBlockRepository.delete_time_block` walked. Its
  `block_assignments` are left alone for the reason given under **student**.

DOUBLE ARCHIVE is an ERROR, not a no-op: `archive()` on an already-archived
root raises `AlreadyArchivedError` naming the event that owns it. A silent
no-op would hand the caller an event id that stamped nothing, and restoring
that event would appear to succeed while changing nothing at all -- the worst
of the available failures, because it looks like it worked.

RESTORING A CHILD WHOSE PARENT IS ARCHIVED is BLOCKED. Putting a goal back
underneath an archived student would produce a row that is active, visible to
no list (its student is hidden) and reachable only by guessing its id. The
error names the parent's event so the caller knows what to restore first.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.archive_event import (
    ARCHIVABLE_ENTITY_TYPES,
    ENTITY_APPOINTMENT,
    ENTITY_GOAL,
    ENTITY_OBJECTIVE,
    ENTITY_PROGRESS_ENTRY,
    ENTITY_STUDENT,
    ENTITY_THERAPY_SESSION,
    ENTITY_TIME_BLOCK,
    ArchiveEvent,
)
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.models.student import Student
from app.models.therapy_session import TherapySession
from app.models.time_block import TimeBlock

# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------
ENTITY_MODELS: dict[str, type] = {
    ENTITY_STUDENT: Student,
    ENTITY_GOAL: IEPGoal,
    ENTITY_OBJECTIVE: GoalObjective,
    ENTITY_PROGRESS_ENTRY: ObjectiveProgressEntry,
    ENTITY_THERAPY_SESSION: TherapySession,
    ENTITY_APPOINTMENT: Appointment,
    ENTITY_TIME_BLOCK: TimeBlock,
}

# The reverse map, used to label counts and to walk every archivable table when
# restoring. Ordered the way a human reads the hierarchy.
MODEL_ENTITY: dict[type, str] = {model: name for name, model in ENTITY_MODELS.items()}

# The key each entity type is counted under in every summary this module
# returns. PLURAL, and deliberately not the entity type itself: the MCP
# sanitizer treats a key called "student" as a field carrying a student's NAME
# and drops it when the surrounding object cannot say which student it is
# (see app/mcp/privacy.py). A count keyed "student" would therefore vanish on
# the way to an agent -- silently, and only for that one line of the summary.
# "students" collides with nothing.
COUNT_LABELS: dict[str, str] = {
    ENTITY_STUDENT: "students",
    ENTITY_GOAL: "goals",
    ENTITY_OBJECTIVE: "objectives",
    ENTITY_PROGRESS_ENTRY: "progressEntries",
    ENTITY_THERAPY_SESSION: "therapySessions",
    ENTITY_APPOINTMENT: "appointments",
    ENTITY_TIME_BLOCK: "timeBlocks",
}

# Human labels for error messages. "goal_objective" is what the table is
# called; "objective" is what a therapist calls it.
ENTITY_LABELS: dict[str, str] = {
    ENTITY_STUDENT: "student",
    ENTITY_GOAL: "goal",
    ENTITY_OBJECTIVE: "objective",
    ENTITY_PROGRESS_ENTRY: "progress entry",
    ENTITY_THERAPY_SESSION: "therapy session",
    ENTITY_APPOINTMENT: "appointment",
    ENTITY_TIME_BLOCK: "time block",
}

# SQL Server refuses a statement with more than 2100 bind parameters, and an
# `IN (...)` over a whole caseload's progress entries gets there. Every id list
# this module builds is chunked through `_chunks` before it reaches a query.
_PARAM_CHUNK = 500


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------
class ArchiveError(Exception):
    """Base class, so a caller can catch every refusal this module makes."""


class UnknownEntityTypeError(ArchiveError):
    pass


class EntityNotFoundError(ArchiveError):
    pass


class AlreadyArchivedError(ArchiveError):
    """The root is already archived. Carries the event that owns it."""

    def __init__(self, message: str, event_id: Optional[int]) -> None:
        super().__init__(message)
        self.event_id = event_id


class AlreadyRestoredError(ArchiveError):
    pass


class ParentStillArchivedError(ArchiveError):
    """Restoring this would leave an orphan under an archived parent."""

    def __init__(self, message: str, parent_event_id: Optional[int]) -> None:
        super().__init__(message)
        self.parent_event_id = parent_event_id


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _chunks(values: Sequence[int]) -> Iterable[Sequence[int]]:
    for start in range(0, len(values), _PARAM_CHUNK):
        yield values[start : start + _PARAM_CHUNK]


def _ids(db: Session, model: type, criterion) -> list[int]:
    return [row[0] for row in db.query(model.id).filter(criterion).all()]


def _ids_in(db: Session, model: type, column, parent_ids: Sequence[int]) -> list[int]:
    """`SELECT id WHERE <column> IN (parents)`, chunked for SQL Server."""
    if not parent_ids:
        return []
    found: list[int] = []
    for chunk in _chunks(parent_ids):
        found.extend(_ids(db, model, column.in_(list(chunk))))
    return found


def _model_for(entity_type: str) -> type:
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise UnknownEntityTypeError(
            f"'{entity_type}' is not an archivable entity type. "
            f"Expected one of: {', '.join(sorted(ARCHIVABLE_ENTITY_TYPES))}."
        )
    return model


def load_entity(db: Session, entity_type: str, entity_id: int) -> Any:
    """The row, archived or not. Raises rather than returning None."""
    model = _model_for(entity_type)
    row = db.query(model).filter(model.id == entity_id).first()
    if row is None:
        raise EntityNotFoundError(
            f"No {ENTITY_LABELS[entity_type]} with id {entity_id}."
        )
    return row


def root_student_id(db: Session, entity_type: str, entity_id: int) -> Optional[int]:
    """The student an entity belongs to, for the caller's access check.

    `None` for a time block, which belongs to a therapist and a school rather
    than to any one child -- the caller decides what to do with that.
    """
    row = load_entity(db, entity_type, entity_id)
    if entity_type == ENTITY_STUDENT:
        return row.id
    if entity_type in (ENTITY_GOAL, ENTITY_THERAPY_SESSION, ENTITY_APPOINTMENT):
        return row.student_id
    if entity_type == ENTITY_OBJECTIVE:
        return row.goal.student_id if row.goal else None
    if entity_type == ENTITY_PROGRESS_ENTRY:
        objective = row.objective
        return objective.goal.student_id if objective and objective.goal else None
    return None


# --------------------------------------------------------------------------
# the cascades
# --------------------------------------------------------------------------
def cascade_targets(
    db: Session, entity_type: str, entity_id: int
) -> list[tuple[type, list[int]]]:
    """Every row an archive of this root reaches, as (model, ids) pairs.

    Includes rows that are ALREADY archived -- the caller filters those out at
    stamp time, and building the full graph here means the count reported to a
    human ("this hides 3 goals") is the shape of the record rather than the
    shape of what happens to be active.

    See the module docstring for why each set is what it is.
    """
    _model_for(entity_type)  # validates the vocabulary

    if entity_type == ENTITY_STUDENT:
        goal_ids = _ids(db, IEPGoal, IEPGoal.student_id == entity_id)
        objective_ids = _ids_in(db, GoalObjective, GoalObjective.goal_id, goal_ids)
        entry_ids = _ids_in(
            db, ObjectiveProgressEntry, ObjectiveProgressEntry.objective_id, objective_ids
        )
        return [
            (Student, [entity_id]),
            (IEPGoal, goal_ids),
            (GoalObjective, objective_ids),
            (ObjectiveProgressEntry, entry_ids),
            (TherapySession, _ids(db, TherapySession, TherapySession.student_id == entity_id)),
            (Appointment, _ids(db, Appointment, Appointment.student_id == entity_id)),
        ]

    if entity_type == ENTITY_GOAL:
        objective_ids = _ids(db, GoalObjective, GoalObjective.goal_id == entity_id)
        entry_ids = _ids_in(
            db, ObjectiveProgressEntry, ObjectiveProgressEntry.objective_id, objective_ids
        )
        return [
            (IEPGoal, [entity_id]),
            (GoalObjective, objective_ids),
            (ObjectiveProgressEntry, entry_ids),
        ]

    if entity_type == ENTITY_OBJECTIVE:
        return [
            (GoalObjective, [entity_id]),
            (
                ObjectiveProgressEntry,
                _ids(
                    db,
                    ObjectiveProgressEntry,
                    ObjectiveProgressEntry.objective_id == entity_id,
                ),
            ),
        ]

    if entity_type == ENTITY_PROGRESS_ENTRY:
        return [(ObjectiveProgressEntry, [entity_id])]

    if entity_type == ENTITY_THERAPY_SESSION:
        # Itself only. The progress entries logged during it belong to an
        # objective and stay active -- see the module docstring.
        return [(TherapySession, [entity_id])]

    if entity_type == ENTITY_APPOINTMENT:
        return [
            (Appointment, [entity_id]),
            (
                TherapySession,
                _ids(db, TherapySession, TherapySession.appointment_id == entity_id),
            ),
        ]

    # ENTITY_TIME_BLOCK
    return [
        (TimeBlock, [entity_id]),
        (Appointment, _ids(db, Appointment, Appointment.time_block_id == entity_id)),
        (
            TherapySession,
            _ids(db, TherapySession, TherapySession.time_block_id == entity_id),
        ),
    ]


def _parent_chain(db: Session, entity_type: str, entity_id: int) -> list[tuple[str, Any]]:
    """The ancestors of a root, nearest first.

    Used only by `restore`: an event's own cascade runs DOWNWARD, so an
    ancestor is never stamped by the event being restored, and any ancestor
    that is archived is archived under some OTHER event.
    """
    row = load_entity(db, entity_type, entity_id)

    if entity_type in (ENTITY_STUDENT, ENTITY_TIME_BLOCK):
        return []

    if entity_type in (ENTITY_GOAL, ENTITY_THERAPY_SESSION, ENTITY_APPOINTMENT):
        student = db.query(Student).filter(Student.id == row.student_id).first()
        return [(ENTITY_STUDENT, student)] if student else []

    if entity_type == ENTITY_OBJECTIVE:
        goal = row.goal
        if goal is None:
            return []
        return [(ENTITY_GOAL, goal)] + _parent_chain(db, ENTITY_GOAL, goal.id)

    # ENTITY_PROGRESS_ENTRY. The therapy session an entry was logged in is
    # deliberately NOT a parent: `therapy_session_id` is nullable and the entry
    # survives the session's archive, so an archived session must not block
    # putting the entry back.
    objective = row.objective
    if objective is None:
        return []
    return [(ENTITY_OBJECTIVE, objective)] + _parent_chain(
        db, ENTITY_OBJECTIVE, objective.id
    )


# --------------------------------------------------------------------------
# archive
# --------------------------------------------------------------------------
def preview(db: Session, entity_type: str, entity_id: int) -> dict[str, int]:
    """What archiving this root would hide, counted per entity type.

    ACTIVE rows only -- this is the number a human is being asked to approve,
    and rows already archived under an older event are not part of the decision.
    Feeds the `confirm=false` refusal summary of every MCP `archive_*` tool.
    """
    counts: dict[str, int] = {}
    for model, ids in cascade_targets(db, entity_type, entity_id):
        if not ids:
            continue
        total = 0
        for chunk in _chunks(ids):
            total += (
                db.query(model.id)
                .filter(model.id.in_(list(chunk)), model.archived_at.is_(None))
                .count()
            )
        if total:
            counts[COUNT_LABELS[MODEL_ENTITY[model]]] = total
    return counts


def archive(
    db: Session,
    user_id: int,
    entity_type: str,
    entity_id: int,
    reason: Optional[str] = None,
) -> ArchiveEvent:
    """Archive a root and its cascade set under one new event.

    Raises `AlreadyArchivedError` if the root is already archived -- see the
    module docstring for why that is an error rather than a no-op.
    """
    root = load_entity(db, entity_type, entity_id)
    if root.archived_at is not None:
        raise AlreadyArchivedError(
            f"{ENTITY_LABELS[entity_type].capitalize()} {entity_id} is already "
            f"archived"
            + (
                f" under archive event {root.archive_event_id}."
                if root.archive_event_id
                else " (archived before archive events were recorded)."
            ),
            root.archive_event_id,
        )

    now = datetime.utcnow()
    event = ArchiveEvent(
        user_id=user_id,
        created_at=now,
        root_entity_type=entity_type,
        root_entity_id=entity_id,
        reason=reason,
    )
    db.add(event)
    db.flush()  # the id every stamp below carries

    for model, ids in cascade_targets(db, entity_type, entity_id):
        if not ids:
            continue
        values: dict[Any, Any] = {
            model.archived_at: now,
            model.archive_event_id: event.id,
        }
        if model is Student:
            # The legacy boolean, kept in lockstep. `_is_archived` is the
            # mapped attribute; the column is still called `is_archived`.
            values[Student._is_archived] = True
        for chunk in _chunks(ids):
            (
                db.query(model)
                .filter(
                    model.id.in_(list(chunk)),
                    # THE RULE. Rows already archived keep their older event.
                    model.archived_at.is_(None),
                )
                .update(values, synchronize_session=False)
            )

    db.commit()
    # `synchronize_session=False` left every loaded instance stale.
    db.expire_all()
    db.refresh(event)
    return event


def archive_many(
    db: Session,
    user_id: int,
    entity_type: str,
    entity_ids: Sequence[int],
    reason: Optional[str] = None,
) -> ArchiveEvent:
    """Archive several roots of the same type under ONE event.

    For the operations a user thinks of as a single act even though the schema
    does not: "delete this appointment series" is one decision by one person,
    and it has to come back as one decision too. N separate events would mean N
    separate restores, each of which could be done and the rest forgotten.

    The event's `root_entity_id` is the first id -- the vocabulary has one root
    and this is the honest approximation. What the event actually holds is on
    the rows, and `event_contents` reports it exactly.

    Ids that are already archived are skipped (the usual rule). If NONE of them
    is active, nothing is archived and `AlreadyArchivedError` is raised rather
    than an event created that stamps nothing.
    """
    model = _model_for(entity_type)
    ids = list(dict.fromkeys(int(i) for i in entity_ids))
    if not ids:
        raise EntityNotFoundError(
            f"No {ENTITY_LABELS[entity_type]} ids given to archive."
        )

    active: list[int] = []
    for chunk in _chunks(ids):
        active.extend(
            _ids(db, model, model.id.in_(list(chunk)) & model.archived_at.is_(None))
        )
    if not active:
        raise AlreadyArchivedError(
            f"Every {ENTITY_LABELS[entity_type]} in that set is already archived.",
            None,
        )

    now = datetime.utcnow()
    event = ArchiveEvent(
        user_id=user_id,
        created_at=now,
        root_entity_type=entity_type,
        root_entity_id=active[0],
        reason=reason,
    )
    db.add(event)
    db.flush()

    for root_id in active:
        for model_cls, target_ids in cascade_targets(db, entity_type, root_id):
            if not target_ids:
                continue
            values: dict[Any, Any] = {
                model_cls.archived_at: now,
                model_cls.archive_event_id: event.id,
            }
            if model_cls is Student:
                values[Student._is_archived] = True
            for chunk in _chunks(target_ids):
                (
                    db.query(model_cls)
                    .filter(
                        model_cls.id.in_(list(chunk)),
                        model_cls.archived_at.is_(None),
                    )
                    .update(values, synchronize_session=False)
                )

    db.commit()
    db.expire_all()
    db.refresh(event)
    return event


# --------------------------------------------------------------------------
# restore
# --------------------------------------------------------------------------
def event_contents(db: Session, event_id: int) -> dict[str, int]:
    """How many rows of each type this event stamped and still owns."""
    counts: dict[str, int] = {}
    for entity_type, model in ENTITY_MODELS.items():
        total = (
            db.query(model.id).filter(model.archive_event_id == event_id).count()
        )
        if total:
            counts[COUNT_LABELS[entity_type]] = total
    return counts


def get_event(db: Session, event_id: int) -> ArchiveEvent:
    event = db.query(ArchiveEvent).filter(ArchiveEvent.id == event_id).first()
    if event is None:
        raise EntityNotFoundError(
            f"No archive event with id {event_id}. List the events to see the "
            f"ids that exist."
        )
    return event


def restore(db: Session, user_id: int, event_id: int) -> dict:
    """Reverse one archive event, and only that event.

    Clears `archived_at` / `archive_event_id` on the rows whose
    `archive_event_id` is this event. Rows archived under a DIFFERENT event --
    including rows that were already archived when this event's cascade ran --
    are untouched, which is what makes the reversal faithful rather than
    approximate.
    """
    event = get_event(db, event_id)
    if event.restored_at is not None:
        raise AlreadyRestoredError(
            f"Archive event {event_id} was already restored on "
            f"{event.restored_at.isoformat()}."
        )

    # No orphan resurrection: every ancestor of the root must be active.
    for parent_type, parent in _parent_chain(
        db, event.root_entity_type, event.root_entity_id
    ):
        if parent is None or parent.archived_at is None:
            continue
        where = (
            f"under archive event {parent.archive_event_id}"
            if parent.archive_event_id
            else "outside any archive event (a legacy archive)"
        )
        raise ParentStillArchivedError(
            f"Archive event {event_id} cannot be restored: the "
            f"{ENTITY_LABELS[event.root_entity_type]}'s "
            f"{ENTITY_LABELS[parent_type]} (id {parent.id}) is still archived "
            f"{where}. Restore that first, then this event.",
            parent.archive_event_id,
        )

    restored: dict[str, int] = {}
    for entity_type, model in ENTITY_MODELS.items():
        values: dict[Any, Any] = {
            model.archived_at: None,
            model.archive_event_id: None,
        }
        if model is Student:
            values[Student._is_archived] = False
        count = (
            db.query(model)
            .filter(model.archive_event_id == event_id)
            .update(values, synchronize_session=False)
        )
        if count:
            restored[COUNT_LABELS[entity_type]] = count

    event.restored_at = datetime.utcnow()
    event.restored_by_user_id = user_id
    db.commit()
    db.expire_all()

    return {
        "eventId": event.id,
        "rootEntityType": event.root_entity_type,
        "rootEntityId": event.root_entity_id,
        "restoredAt": event.restored_at.isoformat(),
        "restoredByUserId": user_id,
        "restored": restored,
        "totalRows": sum(restored.values()),
    }


# --------------------------------------------------------------------------
# listing
# --------------------------------------------------------------------------
def list_events(
    db: Session,
    user_id: Optional[int] = None,
    include_restored: bool = True,
    root_entity_type: Optional[str] = None,
    limit: int = 100,
) -> list[ArchiveEvent]:
    """Archive events, newest first.

    `user_id=None` means every user's events, which is the admin view. A
    non-admin caller passes their own id -- the scoping decision belongs to the
    router and the MCP tool, which know who is asking.
    """
    query = db.query(ArchiveEvent)
    if user_id is not None:
        query = query.filter(ArchiveEvent.user_id == user_id)
    if not include_restored:
        query = query.filter(ArchiveEvent.restored_at.is_(None))
    if root_entity_type is not None:
        _model_for(root_entity_type)
        query = query.filter(ArchiveEvent.root_entity_type == root_entity_type)
    return query.order_by(ArchiveEvent.id.desc()).limit(limit).all()


def list_archived(
    db: Session,
    entity_type: str,
    allowed_student_ids: Optional[list[int]] = None,
    limit: int = 500,
) -> list:
    """Currently-archived rows of one type, newest archive first.

    `allowed_student_ids=None` means "no access filter", the same convention
    the repositories use. A time block has no student, so the filter does not
    apply to it -- documented rather than silently ignored.
    """
    model = _model_for(entity_type)
    query = db.query(model).filter(model.archived_at.isnot(None))

    if allowed_student_ids is not None and entity_type != ENTITY_TIME_BLOCK:
        if not allowed_student_ids:
            return []
        if entity_type == ENTITY_STUDENT:
            query = query.filter(Student.id.in_(allowed_student_ids))
        elif entity_type in (ENTITY_GOAL, ENTITY_THERAPY_SESSION, ENTITY_APPOINTMENT):
            query = query.filter(model.student_id.in_(allowed_student_ids))
        elif entity_type == ENTITY_OBJECTIVE:
            query = query.join(IEPGoal, GoalObjective.goal_id == IEPGoal.id).filter(
                IEPGoal.student_id.in_(allowed_student_ids)
            )
        else:  # ENTITY_PROGRESS_ENTRY
            query = (
                query.join(
                    GoalObjective,
                    ObjectiveProgressEntry.objective_id == GoalObjective.id,
                )
                .join(IEPGoal, GoalObjective.goal_id == IEPGoal.id)
                .filter(IEPGoal.student_id.in_(allowed_student_ids))
            )

    return query.order_by(model.archived_at.desc(), model.id.desc()).limit(limit).all()


def event_summary(db: Session, event: ArchiveEvent) -> dict:
    """One event as JSON, with the counts of what it still holds.

    Carries no names: the root is named by TYPE and ID, and a student's identity
    over MCP is their alias, which the sanitizer substitutes on the way out.
    """
    return {
        "eventId": event.id,
        "userId": event.user_id,
        "createdAt": event.created_at.isoformat() if event.created_at else None,
        "rootEntityType": event.root_entity_type,
        "rootEntityId": event.root_entity_id,
        "reason": event.reason,
        "restored": event.restored_at is not None,
        "restoredAt": event.restored_at.isoformat() if event.restored_at else None,
        "restoredByUserId": event.restored_by_user_id,
        "contents": event_contents(db, event.id),
    }
