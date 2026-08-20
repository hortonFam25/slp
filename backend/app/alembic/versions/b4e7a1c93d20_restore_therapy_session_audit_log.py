"""Restore the therapy-session audit trail.

The production catalog for `slpdb_2` showed a half-demolished audit system:

* `trg_therapy_sessions_audit_safe` and `trg_session_objectives_audit_safe`
  both still existed, both with `is_disabled = 1`;
* `therapy_session_audit_log`, the table they insert into, did NOT exist;
* `vw_recent_audit_changes`, `sp_GetStudentAuditHistory` and
  `sp_LogTherapySessionChange` were all still there, referencing that missing
  table.

So the table had been dropped and the triggers switched off to stop the errors,
leaving the view and both procedures orphaned. Nothing in the repository knew
the table had ever existed, which is how it stayed broken.

This revision brings the table back under schema management (there is now a
model, `app/models/therapy_session_audit_log.py`, so `create_all` produces it
too) and re-enables the triggers where they exist.

The column list is the union of what the two triggers' INSERT lists name and
what the orphaned modules read back: the view selects change_reason,
change_timestamp, database_user, field_name, id, new_value, old_value,
operation_type, record_id and table_name; `sp_LogTherapySessionChange` also
writes user_context and change_reason. `field_name` is NULLABLE because one of
the trigger INSERT lists omits it entirely.

Portability: the ENABLE TRIGGER step is guarded on the mssql dialect AND on the
trigger actually being present in `sys.triggers`. On sqlite — and on a
dev-fresh SQL Server database that never had these triggers — it is a no-op,
not an error. The table creation itself is dialect-neutral.

Revision ID: b4e7a1c93d20
Revises: c5a91b3e77d4
Create Date: 2026-08-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision: str = "b4e7a1c93d20"
down_revision: Union[str, None] = "c5a91b3e77d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The triggers this revision re-enables, with the table each is attached to.
_AUDIT_TRIGGERS = (
    ("trg_therapy_sessions_audit_safe", "therapy_sessions"),
    ("trg_session_objectives_audit_safe", "session_objectives"),
)

# UnicodeText renders NTEXT on SQL Server unless the dialect resolved
# `deprecate_large_types` against a live server. NTEXT is deprecated and refuses
# most string operators, so pin NVARCHAR(max) explicitly and leave sqlite on
# TEXT. Identical to what the model declares.
_AUDIT_TEXT = sa.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")


def _set_trigger_state(enable: bool) -> None:
    """ENABLE or DISABLE both audit triggers, if this is SQL Server and they exist.

    Two guards, because both cases are real: `slpdb_dev` is built by
    `create_all` and has never had a trigger, and the sqlite path has no
    `sys.triggers` to ask. Neither should fail the migration.
    """
    bind = op.get_bind()
    if bind.dialect.name != "mssql":
        return

    verb = "ENABLE" if enable else "DISABLE"
    for trigger_name, table_name in _AUDIT_TRIGGERS:
        exists = bind.exec_driver_sql(
            "SELECT COUNT(*) FROM sys.triggers WHERE name = ?", (trigger_name,)
        ).scalar()
        if not exists:
            continue
        # Object names come from the module-level tuple above, never from user
        # input, so the interpolation here is not a parameterisation gap —
        # ENABLE TRIGGER takes an identifier, which cannot be a bind parameter.
        bind.exec_driver_sql(f"{verb} TRIGGER [{trigger_name}] ON [{table_name}]")


def upgrade() -> None:
    op.create_table(
        "therapy_session_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        # The audited table's name and its own primary key. Deliberately NOT a
        # foreign key: audit rows have to outlive the rows they describe.
        sa.Column("table_name", sa.Unicode(length=128), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        # Nullable — one trigger's INSERT list omits it. See the docstring.
        sa.Column("field_name", sa.Unicode(length=128), nullable=True),
        sa.Column("old_value", _AUDIT_TEXT, nullable=True),
        sa.Column("new_value", _AUDIT_TEXT, nullable=True),
        sa.Column("operation_type", sa.Unicode(length=16), nullable=False),
        sa.Column(
            "change_timestamp",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("change_reason", _AUDIT_TEXT, nullable=True),
        sa.Column("user_context", sa.Unicode(length=200), nullable=True),
        sa.Column("database_user", sa.Unicode(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_therapy_session_audit_log_id"),
        "therapy_session_audit_log",
        ["id"],
        unique=False,
    )
    # How sp_GetStudentAuditHistory and the view read: narrow to one record of
    # one table, or scan by recency.
    op.create_index(
        "ix_therapy_session_audit_log_table_record",
        "therapy_session_audit_log",
        ["table_name", "record_id"],
        unique=False,
    )
    op.create_index(
        "ix_therapy_session_audit_log_change_timestamp",
        "therapy_session_audit_log",
        ["change_timestamp"],
        unique=False,
    )

    # Only now that the destination exists is it safe to let them fire again.
    _set_trigger_state(enable=True)


def downgrade() -> None:
    # Reverse order: silence the writers before removing what they write to,
    # otherwise every INSERT into therapy_sessions starts failing.
    _set_trigger_state(enable=False)

    op.drop_index(
        "ix_therapy_session_audit_log_change_timestamp",
        table_name="therapy_session_audit_log",
    )
    op.drop_index(
        "ix_therapy_session_audit_log_table_record",
        table_name="therapy_session_audit_log",
    )
    op.drop_index(
        op.f("ix_therapy_session_audit_log_id"),
        table_name="therapy_session_audit_log",
    )
    op.drop_table("therapy_session_audit_log")
