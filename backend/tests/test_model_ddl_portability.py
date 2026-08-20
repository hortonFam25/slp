"""The models' DDL must compile on both dialects this project runs against.

Azure SQL is production; sqlite is what the tests, ``scripts/seed_dev.py`` and a
developer's local run use. Both used to be served by a
``before_cursor_execute`` shim in ``conftest.py`` that rewrote the
SQL-Server-only ``GETDATE()`` into ``CURRENT_TIMESTAMP`` on its way to the
driver. ``server_default=func.now()`` makes that unnecessary — SQLAlchemy
renders the right thing per dialect — and these tests keep it that way.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import mssql, sqlite
from sqlalchemy.schema import CreateTable


@pytest.fixture(scope="module")
def metadata():
    import app.models  # noqa: F401  — registers every mapper
    from app.db.base import Base

    return Base.metadata


def _all_ddl(metadata, dialect):
    return "\n".join(str(CreateTable(t).compile(dialect=dialect)) for t in metadata.sorted_tables)


@pytest.mark.parametrize("dialect_name", ["mssql", "sqlite"])
def test_no_table_hardcodes_getdate(metadata, dialect_name):
    """``GETDATE()`` must not appear in emitted DDL on either dialect.

    A literal ``text("GETDATE()")`` default renders verbatim everywhere, which
    is precisely what broke sqlite's ``create_all`` (``near "(": syntax
    error``). ``func.now()`` is dialect-aware, so nothing should be hard-coded.
    """
    dialect = {"mssql": mssql.dialect(), "sqlite": sqlite.dialect()}[dialect_name]
    assert "GETDATE" not in _all_ddl(metadata, dialect).upper()


@pytest.mark.parametrize(
    "table_name",
    ["students", "appointments", "time_blocks", "therapy_sessions"],
)
def test_timestamp_defaults_render_current_timestamp(metadata, table_name):
    """Representative tables get a real server-side default on both dialects.

    ``func.now()`` compiles to ``CURRENT_TIMESTAMP`` under both — that is the
    ANSI spelling, and on SQL Server it is the T-SQL equivalent of ``GETDATE()``
    (same type, same precision, both nondeterministic).
    """
    table = metadata.tables[table_name]
    for dialect in (mssql.dialect(), sqlite.dialect()):
        ddl = str(CreateTable(table).compile(dialect=dialect))
        for column in ("created_date", "modified_date"):
            line = next(ln for ln in ddl.splitlines() if ln.strip().startswith(column))
            assert "CURRENT_TIMESTAMP" in line, (dialect.name, table_name, column, line)


def test_create_all_runs_on_a_bare_sqlite_file(tmp_path, metadata):
    """``create_all`` against an untouched sqlite engine — no rewrite hook.

    The engine is built here rather than reusing the app's, so no event listener
    registered elsewhere in the suite can mask a regression.
    """
    from sqlalchemy import create_engine, inspect, text

    db = tmp_path / "portability.db"
    engine = create_engine(f"sqlite:///{db.as_posix()}")
    metadata.create_all(bind=engine)

    assert "students" in inspect(engine).get_table_names()

    # And the default actually fires: an INSERT that names no timestamp still
    # lands a value in a NOT NULL column.
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO students (student_alias, first, last) VALUES ('ddl-probe', 'A', 'B')")
        )
        stamped = conn.execute(
            text("SELECT created_date FROM students WHERE student_alias = 'ddl-probe'")
        ).scalar()
    assert stamped is not None
