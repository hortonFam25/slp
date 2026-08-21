"""One archive action, and the columns that let a row point back at it.

The rule this table exists to enforce: **nothing in this application deletes
clinical data any more.** Every route, repository method and MCP tool that used
to issue a DELETE now stamps rows instead, and every stamp names the
`archive_events` row that caused it. Because the stamp carries the event id and
not merely a timestamp, an archive is *reversible as a unit*: restore clears
exactly the rows this event stamped, and nothing else.

That last clause is the whole design. Consider a goal archived in September and
its student archived in January. If the January cascade re-stamped the goal, a
restore of the January event would resurrect a goal the therapist had already
retired -- silently, and with no way to tell it apart from the rest. So the
cascade only ever stamps rows that are CURRENTLY ACTIVE (`archived_at IS
NULL`); a row already archived under an older event keeps that older event, and
comes back only when *that* event is restored. See `app/services/archive.py`.

Two columns per archivable table:

* ``archived_at`` -- NULL means active. This is the single source of truth for
  "is this row visible", and every default query path filters on it.
* ``archive_event_id`` -- the event that archived it. NULL for a row archived
  by something older than this framework (see the ``students.is_archived``
  backfill in revision ``a1c4e8b60d37``), which is why the *timestamp* and not
  the event is what decides visibility.

``students.is_archived`` predates all of this and is still in the schema, still
in the REST payload and still read by the React app. It is now a hybrid over
``archived_at`` -- see ``app/models/student.py`` -- so the boolean the API emits
and the column the service stamps can never disagree.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, UnicodeText, func
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import declared_attr, relationship

from app.db.base import Base

# NVARCHAR(max) on SQL Server rather than the NTEXT that a bare UnicodeText
# renders when the dialect has not resolved `deprecate_large_types` against a
# live server. Same trick as b4e7a1c93d20 and c9f2a7d81b45.
_LARGE_TEXT = UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")


# The `root_entity_type` vocabulary. Kept as plain strings rather than a native
# enum because SQL Server has no enum type and a CHECK constraint here would
# make adding an archivable entity a migration instead of a dict entry.
ENTITY_STUDENT = "student"
ENTITY_GOAL = "goal"
ENTITY_OBJECTIVE = "objective"
ENTITY_PROGRESS_ENTRY = "progress_entry"
ENTITY_THERAPY_SESSION = "therapy_session"
ENTITY_APPOINTMENT = "appointment"
ENTITY_TIME_BLOCK = "time_block"
# The row that says which disability category a child qualifies under. Singular
# on purpose: the table is `student_eligibilities`, but every other member of
# this vocabulary names ONE row, and `list_archive_events(root_entity_type=...)`
# reads better for it.
ENTITY_STUDENT_ELIGIBILITY = "student_eligibility"

ARCHIVABLE_ENTITY_TYPES = (
    ENTITY_STUDENT,
    ENTITY_GOAL,
    ENTITY_OBJECTIVE,
    ENTITY_PROGRESS_ENTRY,
    ENTITY_THERAPY_SESSION,
    ENTITY_APPOINTMENT,
    ENTITY_TIME_BLOCK,
    ENTITY_STUDENT_ELIGIBILITY,
)


class ArchiveEvent(Base):
    """One user's decision to archive one thing, and everything under it.

    `root_entity_type` / `root_entity_id` name what the user actually asked to
    archive. The rows stamped with this event's id are that root plus its
    cascade set -- which is derivable from the root, but is recorded on the rows
    themselves so that a restore never has to re-derive a graph that has since
    changed shape.

    `restored_at IS NULL` means the archive is still in force. A restored event
    is kept, not deleted: it is the record that the data was archived on a date
    and put back on another, which is exactly the kind of thing an IEP audit
    asks about.
    """

    __tablename__ = "archive_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    root_entity_type = Column(Unicode(40), nullable=False, index=True)
    root_entity_id = Column(Integer, nullable=False, index=True)

    # Free text the therapist typed, or an agent composed. NEVER assume it is
    # free of student names -- the MCP sanitizer scrubs it on the way out.
    reason = Column(_LARGE_TEXT, nullable=True)

    restored_at = Column(DateTime, nullable=True, index=True)
    restored_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    restored_by_user = relationship("User", foreign_keys=[restored_by_user_id])

    @property
    def is_restored(self) -> bool:
        return self.restored_at is not None


class ArchivableMixin:
    """The two columns every archivable table carries.

    A mixin rather than eight copy-pasted pairs so that "what does archivable
    mean" has one answer, and so `app/services/archive.py` can assert a model is
    archivable by an isinstance check on the class rather than by hoping.

    `declared_attr` is required: a bare `Column` object cannot be shared between
    mapped classes.
    """

    @declared_attr
    def archived_at(cls):  # noqa: N805 - SQLAlchemy mixin convention
        return Column(DateTime, nullable=True)

    @declared_attr
    def archive_event_id(cls):  # noqa: N805 - SQLAlchemy mixin convention
        return Column(
            Integer,
            ForeignKey("archive_events.id"),
            nullable=True,
            index=True,
        )
