"""Add archive_events and the archived_at / archive_event_id columns.

This is the schema half of "SLP Pro no longer deletes clinical data". See
`app/models/archive_event.py` for the argument and `app/services/archive.py`
for the behaviour; what happens here is:

1. `archive_events` -- one row per archive action a user took, naming the ROOT
   entity they asked to archive and (once reversed) when and by whom it was
   restored. Restored events are kept, never deleted: "archived on the 4th, put
   back on the 9th" is the sort of thing an IEP audit asks about.

2. Two columns on each of the seven archivable tables. `archived_at IS NULL`
   means active and is what every default query path filters on;
   `archive_event_id` names the event that stamped the row, which is what makes
   a restore surgical instead of a guess.

3. A backfill for `students.is_archived`, the one archive flag that predates all
   of this (revision 8f054481089d). The column stays -- it is in the REST
   payload and the React app reads it -- but the ORM now treats `archived_at` as
   the truth and keeps `is_archived` in sync on write, so the two rows of data
   have to agree before the first request lands. Legacy archives get
   `archive_event_id = NULL`: nobody recorded who archived them or why, and
   inventing an event to say so would be a lie in an audit table.

FOREIGN KEYS AND SQLITE. `op.create_foreign_key` is not implementable on
SQLite -- the dialect has no ALTER for constraints -- and alembic raises rather
than pretending. SQL Server needs the constraint NAMED, because dropping a
column on SQL Server means dropping its constraints first and an
auto-generated name cannot be written down in a downgrade. So the FK is created
under a dialect guard. On SQLite the column is a plain integer at the migration
level; the model still declares the relationship, so a dev database built by
`create_all` has the real constraint and production (SQL Server) gets it here.

Revision ID: a1c4e8b60d37
Revises: c9f2a7d81b45
Create Date: 2026-08-20 00:00:00.000000
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision: str = "a1c4e8b60d37"
down_revision: Union[str, None] = "c9f2a7d81b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Identical to what the model declares -- NVARCHAR(max), not the deprecated
# NTEXT a bare UnicodeText renders on SQL Server.
_LARGE_TEXT = sa.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")

# Every table that gains the pair, and the name its FK constraint gets.
ARCHIVABLE_TABLES: tuple[str, ...] = (
    "students",
    "iep_goals",
    "goal_objectives",
    "objective_progress_entries",
    "therapy_sessions",
    "appointments",
    "time_blocks",
)

# The timestamp written into `students.archived_at` for rows that were already
# is_archived=1 when this migration ran. A FIXED, obviously-artificial instant
# rather than "now": these students were archived on dates nobody recorded, and
# stamping them all with the deploy time would read as a mass archive that never
# happened. 2000-01-01 is before the first row in this database by years, so it
# sorts where a legacy record belongs and is recognisable on sight as a
# backfill rather than an event.
BACKFILL_TIMESTAMP = datetime(2000, 1, 1, 0, 0, 0)


def _fk_name(table: str) -> str:
    return f"fk_{table}_archive_event_id"


def _index_name(table: str) -> str:
    return f"ix_{table}_archive_event_id"


def upgrade() -> None:
    op.create_table(
        "archive_events",
        sa.Column("id", sa.Integer(), nullable=False),
        # Who archived it. NOT NULL: an archive with no actor is not an audit
        # record, it is a rumour.
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # 'student' | 'goal' | 'objective' | 'progress_entry' |
        # 'therapy_session' | 'appointment' | 'time_block'. Plain text, not an
        # enum: SQL Server has none, and a CHECK constraint would make adding an
        # archivable entity a migration rather than a dict entry.
        sa.Column("root_entity_type", sa.Unicode(length=40), nullable=False),
        sa.Column("root_entity_id", sa.Integer(), nullable=False),
        sa.Column("reason", _LARGE_TEXT, nullable=True),
        # NULL means the archive is still in force.
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.Column("restored_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["restored_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_archive_events_id"), "archive_events", ["id"])
    op.create_index(op.f("ix_archive_events_user_id"), "archive_events", ["user_id"])
    op.create_index(
        op.f("ix_archive_events_root_entity_type"), "archive_events", ["root_entity_type"]
    )
    op.create_index(
        op.f("ix_archive_events_root_entity_id"), "archive_events", ["root_entity_id"]
    )
    # "What is still archived" is the commonest question asked of this table.
    op.create_index(op.f("ix_archive_events_restored_at"), "archive_events", ["restored_at"])

    is_sqlite = op.get_bind().dialect.name == "sqlite"

    for table in ARCHIVABLE_TABLES:
        op.add_column(table, sa.Column("archived_at", sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column("archive_event_id", sa.Integer(), nullable=True))
        op.create_index(_index_name(table), table, ["archive_event_id"])
        if not is_sqlite:
            op.create_foreign_key(
                _fk_name(table),
                table,
                "archive_events",
                ["archive_event_id"],
                ["id"],
            )

    # ---- backfill: students.is_archived -> students.archived_at ----------
    # `archive_event_id` stays NULL, deliberately. See the module docstring.
    op.execute(
        sa.text(
            "UPDATE students SET archived_at = :ts "
            "WHERE is_archived = 1 AND archived_at IS NULL"
        ).bindparams(ts=BACKFILL_TIMESTAMP)
    )


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    # Nothing to undo for the backfill: dropping `archived_at` takes it with
    # it, and `is_archived` -- which the backfill READ and never wrote -- is
    # left exactly as it was found.
    for table in ARCHIVABLE_TABLES:
        if not is_sqlite:
            op.drop_constraint(_fk_name(table), table, type_="foreignkey")
        op.drop_index(_index_name(table), table_name=table)
        op.drop_column(table, "archive_event_id")
        op.drop_column(table, "archived_at")

    op.drop_index(op.f("ix_archive_events_restored_at"), table_name="archive_events")
    op.drop_index(op.f("ix_archive_events_root_entity_id"), table_name="archive_events")
    op.drop_index(op.f("ix_archive_events_root_entity_type"), table_name="archive_events")
    op.drop_index(op.f("ix_archive_events_user_id"), table_name="archive_events")
    op.drop_index(op.f("ix_archive_events_id"), table_name="archive_events")
    op.drop_table("archive_events")
