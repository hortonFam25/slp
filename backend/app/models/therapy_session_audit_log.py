"""The therapy-session audit trail.

Rows here are written by SQL Server triggers, not by the application. Two of
them exist in production:

* ``trg_therapy_sessions_audit_safe`` on ``therapy_sessions``
* ``trg_session_objectives_audit_safe`` on ``session_objectives``

plus ``sp_LogTherapySessionChange``, which writes a row on demand and is the
only writer that fills ``user_context``.

This model is here so the table is schema-managed — created by ``create_all``
in development and by the migration that re-introduced it in production, rather
than existing only as a hand-made object nobody's migrations knew about. The
application does not insert into it; reading it is what the
``vw_recent_audit_changes`` view and ``sp_GetStudentAuditHistory`` are for.

Why the column set looks the way it does: it is the union of what the two
triggers' INSERT lists name and what the view and procedures read back.
``field_name`` in particular is nullable because one of the trigger INSERT
lists omits it — a whole-row operation (a DELETE, say) records no single field.

The triggers are SQL Server only. On sqlite there is nothing to fire, so the
table is created and simply stays empty; the migration's ENABLE TRIGGER step is
a no-op off mssql.
"""

from sqlalchemy import Column, DateTime, Index, Integer, Unicode, UnicodeText, func
from sqlalchemy.dialects import mssql

from app.db.base import Base

# UnicodeText alone renders NTEXT on SQL Server unless the dialect's
# `deprecate_large_types` has been resolved against a live connection. NTEXT is
# deprecated and refuses most string operators, so the variant pins NVARCHAR(max)
# — matching the VARCHAR(max) the rest of this schema's Text columns get — and
# leaves sqlite on plain TEXT. The migration declares the same thing.
_AuditText = UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")


class TherapySessionAuditLog(Base):
    __tablename__ = "therapy_session_audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # What was touched. `table_name` is the source table's name as the trigger
    # spells it; `record_id` is that table's own primary key, not a foreign key
    # — audit rows outlive the rows they describe, so a real FK would either
    # block deletes or cascade the history away.
    table_name = Column(Unicode(128), nullable=False)
    record_id = Column(Integer, nullable=False)

    # Nullable on purpose: see the module docstring. A per-column trigger names
    # the field it saw change; a whole-row one has nothing to put here.
    field_name = Column(Unicode(128), nullable=True)

    # Values are stringified by the trigger before they land here, so a single
    # pair of text columns covers every column type in the audited tables.
    old_value = Column(_AuditText, nullable=True)
    new_value = Column(_AuditText, nullable=True)

    # INSERT / UPDATE / DELETE, as the trigger writes it.
    operation_type = Column(Unicode(16), nullable=False)
    change_timestamp = Column(DateTime, nullable=False, server_default=func.now())

    # Free text. `sp_LogTherapySessionChange` is the caller that supplies both
    # of these; the triggers leave them NULL.
    change_reason = Column(_AuditText, nullable=True)
    user_context = Column(Unicode(200), nullable=True)

    # SUSER_SNAME()/ORIGINAL_LOGIN() as captured at write time.
    database_user = Column(Unicode(128), nullable=True)

    __table_args__ = (
        # The lookup `sp_GetStudentAuditHistory` and the view both do: narrow to
        # one row of one table, then order by time.
        Index("ix_therapy_session_audit_log_table_record", "table_name", "record_id"),
        # `vw_recent_audit_changes` is a straight recency scan.
        Index("ix_therapy_session_audit_log_change_timestamp", "change_timestamp"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TherapySessionAuditLog id={self.id} {self.operation_type} "
            f"{self.table_name}.{self.record_id} field={self.field_name!r}>"
        )
