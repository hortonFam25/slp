"""Add the archive columns to student_eligibilities.

`a1c4e8b60d37` gave `archived_at` / `archive_event_id` to seven tables. It
missed one: `student_eligibilities`. So
`DELETE /api/eligibilities/students/{id}` went on removing the row outright --
the last hard delete of clinical data left in the application.

An eligibility determination is a legal finding about a child: which disability
category they qualify under, and from when. "This was taken off the record on
the 4th" and "this never happened" are different facts, and only one of them is
recoverable. This revision makes the eighth table archivable, on exactly the
terms the other seven got: two nullable columns, an index on the event id, and
the foreign key back to `archive_events`.

The columns are the whole change. There is no backfill: nothing in this table
was ever archived before, because before this there was no archive for it --
every row that a therapist "removed" is already gone, and no column here can
say so. `archived_at IS NULL` on every existing row is therefore true rather
than merely convenient.

`eligibility_categories` does NOT get the pair, deliberately. It is a shared
lookup -- the same handful of rows every child's eligibility points at -- and
archiving one child's determination must never touch a category the rest of the
caseload uses.

FOREIGN KEYS AND SQLITE. Same guard as `a1c4e8b60d37`, for the same two
reasons. `op.create_foreign_key` is not implementable on SQLite (the dialect has
no ALTER for constraints, and alembic raises rather than pretending), and SQL
Server needs the constraint NAMED so that a downgrade has a name to write down
instead of an auto-generated one. On SQLite the column is a plain integer at the
migration level; the model declares the relationship, so a dev database built by
`create_all` has the real constraint and production (SQL Server) gets it here.

OPERATOR-RUN. Adding a FOREIGN KEY to a populated table makes SQL Server
validate the existing rows, which needs SELECT on that table -- and the workflow
identity is schema-only by design. Run this through
`backend/scripts/db_migrate.py upgrade --target ...`, as `a1c4e8b60d37` was.
Its non-destructive guard passes: the upgrade below only adds.

Revision ID: d3f8b2a70c19
Revises: a1c4e8b60d37
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f8b2a70c19"
down_revision: Union[str, None] = "a1c4e8b60d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The eighth archivable table, named the same way `a1c4e8b60d37` names its
# seven so the two lists read as one list.
ARCHIVABLE_TABLES: tuple[str, ...] = ("student_eligibilities",)


def _fk_name(table: str) -> str:
    return f"fk_{table}_archive_event_id"


def _index_name(table: str) -> str:
    return f"ix_{table}_archive_event_id"


def upgrade() -> None:
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


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    for table in ARCHIVABLE_TABLES:
        if not is_sqlite:
            op.drop_constraint(_fk_name(table), table, type_="foreignkey")
        op.drop_index(_index_name(table), table_name=table)
        op.drop_column(table, "archive_event_id")
        op.drop_column(table, "archived_at")
