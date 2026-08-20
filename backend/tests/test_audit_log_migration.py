"""Cover the therapy-session audit table and the trigger-toggling migration.

The migration's ENABLE TRIGGER branch only runs against SQL Server, which no
test here may touch. It is exercised with a stand-in bind instead — the point
under test is the pair of guards (dialect is mssql AND the trigger actually
exists in sys.triggers), and that is decided entirely in Python.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "alembic"
    / "versions"
    / "b4e7a1c93d20_restore_therapy_session_audit_log.py"
)


@pytest.fixture(scope="module")
def migration():
    """Import the revision module directly.

    ``app/alembic/versions`` is not a package, so it is loaded by path rather
    than imported by name.
    """
    spec = importlib.util.spec_from_file_location("_rev_b4e7a1c93d20", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _RecordingBind:
    """Minimal stand-in for the Connection alembic hands the migration.

    Records every statement, and answers the ``sys.triggers`` probe from
    ``existing_triggers``.
    """

    def __init__(self, dialect_name: str, existing_triggers: set[str]):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.existing_triggers = existing_triggers
        self.statements: list[tuple[str, tuple]] = []

    def exec_driver_sql(self, statement, parameters=()):
        self.statements.append((statement, parameters))
        if "sys.triggers" in statement:
            (name,) = parameters
            return SimpleNamespace(scalar=lambda: 1 if name in self.existing_triggers else 0)
        return SimpleNamespace(scalar=lambda: None)


@pytest.fixture()
def patched_op(migration, monkeypatch):
    """Point the migration's ``op.get_bind()`` at a bind we control."""

    def _install(bind):
        monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
        return bind

    return _install


def test_revision_chains_onto_the_expected_head(migration):
    assert migration.revision == "b4e7a1c93d20"
    assert migration.down_revision == "c5a91b3e77d4"


def test_sqlite_issues_no_trigger_sql(migration, patched_op):
    """The whole point of the dialect guard: sqlite has no sys.triggers to ask."""
    bind = patched_op(_RecordingBind("sqlite", set()))
    migration._set_trigger_state(enable=True)
    assert bind.statements == []


def test_mssql_without_the_triggers_only_probes(migration, patched_op):
    """A dev-fresh SQL Server DB built by create_all has never had these triggers.

    It must come out a no-op — the probe runs, no ENABLE follows, nothing raises.
    """
    bind = patched_op(_RecordingBind("mssql", set()))
    migration._set_trigger_state(enable=True)

    assert len(bind.statements) == 2, bind.statements
    assert all("sys.triggers" in stmt for stmt, _ in bind.statements)
    assert not any("ENABLE TRIGGER" in stmt for stmt, _ in bind.statements)


def test_mssql_enables_each_trigger_that_exists(migration, patched_op):
    bind = patched_op(
        _RecordingBind(
            "mssql",
            {"trg_therapy_sessions_audit_safe", "trg_session_objectives_audit_safe"},
        )
    )
    migration._set_trigger_state(enable=True)

    issued = [stmt for stmt, _ in bind.statements if "TRIGGER" in stmt and "sys." not in stmt]
    assert issued == [
        "ENABLE TRIGGER [trg_therapy_sessions_audit_safe] ON [therapy_sessions]",
        "ENABLE TRIGGER [trg_session_objectives_audit_safe] ON [session_objectives]",
    ]


def test_mssql_enables_only_the_trigger_that_exists(migration, patched_op):
    """Prod has both, but the guard is per-trigger, not all-or-nothing."""
    bind = patched_op(_RecordingBind("mssql", {"trg_session_objectives_audit_safe"}))
    migration._set_trigger_state(enable=True)

    issued = [stmt for stmt, _ in bind.statements if "TRIGGER" in stmt and "sys." not in stmt]
    assert issued == [
        "ENABLE TRIGGER [trg_session_objectives_audit_safe] ON [session_objectives]"
    ]


def test_downgrade_disables_rather_than_enables(migration, patched_op):
    bind = patched_op(
        _RecordingBind(
            "mssql",
            {"trg_therapy_sessions_audit_safe", "trg_session_objectives_audit_safe"},
        )
    )
    migration._set_trigger_state(enable=False)

    issued = [stmt for stmt, _ in bind.statements if "TRIGGER" in stmt and "sys." not in stmt]
    assert issued == [
        "DISABLE TRIGGER [trg_therapy_sessions_audit_safe] ON [therapy_sessions]",
        "DISABLE TRIGGER [trg_session_objectives_audit_safe] ON [session_objectives]",
    ]


# --------------------------------------------------------------------------- model


def test_create_all_includes_the_audit_table():
    import app.models  # noqa: F401
    from app.db.base import Base

    assert "therapy_session_audit_log" in Base.metadata.tables


def test_field_name_is_nullable_but_the_required_columns_are_not():
    """One trigger's INSERT list omits field_name — a NOT NULL would reject it."""
    import app.models  # noqa: F401
    from app.db.base import Base

    table = Base.metadata.tables["therapy_session_audit_log"]
    assert table.c.field_name.nullable is True
    for optional in ("old_value", "new_value", "change_reason", "user_context", "database_user"):
        assert table.c[optional].nullable is True, optional
    for required in ("table_name", "record_id", "operation_type", "change_timestamp"):
        assert table.c[required].nullable is False, required


def test_the_view_and_procs_can_still_find_every_column_they_read():
    """Column set is derived from the orphaned modules — pin it so it stays complete.

    ``vw_recent_audit_changes`` selects the first ten;
    ``sp_LogTherapySessionChange`` additionally writes ``user_context``.
    """
    import app.models  # noqa: F401
    from app.db.base import Base

    read_by_view = {
        "change_reason",
        "change_timestamp",
        "database_user",
        "field_name",
        "id",
        "new_value",
        "old_value",
        "operation_type",
        "record_id",
        "table_name",
    }
    table = Base.metadata.tables["therapy_session_audit_log"]
    assert read_by_view <= set(table.c.keys())
    assert "user_context" in table.c


def test_large_text_columns_pin_nvarchar_max_on_sql_server():
    """NTEXT is deprecated and refuses most string operators; NVARCHAR(max) does not."""
    from sqlalchemy.dialects import mssql, sqlite
    from sqlalchemy.schema import CreateTable

    import app.models  # noqa: F401
    from app.db.base import Base

    table = Base.metadata.tables["therapy_session_audit_log"]

    mssql_ddl = str(CreateTable(table).compile(dialect=mssql.dialect()))
    # Word-boundary match: the column named `user_context` ends in the letters
    # "ntext", so a plain substring check passes for the wrong reason.
    assert not re.search(r"\bNTEXT\b", mssql_ddl.upper())
    assert mssql_ddl.upper().count("NVARCHAR(MAX)") == 3  # old_value, new_value, change_reason

    sqlite_ddl = str(CreateTable(table).compile(dialect=sqlite.dialect()))
    assert "NVARCHAR" not in sqlite_ddl.upper()
