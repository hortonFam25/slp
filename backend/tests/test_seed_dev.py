"""The database dev-tooling gate.

Two things are worth testing about tooling that can write to a database, and
only two:

1. **the guards** -- ``seed_dev.assert_seedable`` and
   ``provision_dev_db._assert_dev_database`` are the only things standing
   between a mistyped environment variable and fake data landing in
   ``slpdb_2``. They are tested against fake connections that claim to be
   production, because the whole point is that they refuse without needing a
   real server to refuse against.

2. **that the seeder actually runs end to end** -- against a throwaway sqlite
   file: it builds the schema, inserts in foreign-key order, produces the row
   counts ``seed_dev.PLAN`` promises, and survives ``--reset`` followed by a
   re-seed.

Plus the offline halves of provision_dev_db: the catalog-only enforcement (no
statement this tool sends prod may touch a user table) and the diff generator,
neither of which needs a connection at all.

Runtime is roughly two seconds; it stays in the default CI run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
for path in (str(BACKEND_DIR), str(SCRIPTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import provision_dev_db  # noqa: E402
import seed_dev  # noqa: E402


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def keys(self):
        return ["database_name"]

    def fetchall(self):
        return [(self._value,)]


class _FakeDialect:
    def __init__(self, name):
        self.name = name


class FakeConnection:
    """The smallest thing the guards accept: a dialect and an execute()."""

    def __init__(self, dialect_name: str, database_name: str = "slpdb_2"):
        self.dialect = _FakeDialect(dialect_name)
        self.database_name = database_name
        self.statements: list = []

    def execute(self, statement, *args, **kwargs):
        self.statements.append(str(statement))
        return _FakeResult(self.database_name)


# ---------------------------------------------------------------------------
# seed_dev: the guard
# ---------------------------------------------------------------------------


def test_guard_blocks_production_by_name():
    """The failure this whole file exists for."""
    connection = FakeConnection("mssql", database_name="slpdb_2")
    with pytest.raises(seed_dev.GuardViolation) as excinfo:
        seed_dev.assert_seedable(connection)
    assert "slpdb_2" in str(excinfo.value)


@pytest.mark.parametrize("wrong_name", ["slpdb", "slpdb_2", "SLPDB_DEV", "slpdb_dev2", "master"])
def test_guard_blocks_every_name_that_is_not_exactly_slpdb_dev(wrong_name):
    with pytest.raises(seed_dev.GuardViolation):
        seed_dev.assert_seedable(FakeConnection("mssql", database_name=wrong_name))


def test_guard_allows_slpdb_dev():
    assert seed_dev.assert_seedable(FakeConnection("mssql", database_name="slpdb_dev")) == "slpdb_dev"


def test_guard_asks_the_server_not_the_caller():
    """DB_NAME() is what decides -- not an argument, not an env var."""
    connection = FakeConnection("mssql", database_name="slpdb_dev")
    seed_dev.assert_seedable(connection)
    assert any("DB_NAME()" in statement for statement in connection.statements), connection.statements


def test_guard_allows_sqlite():
    assert seed_dev.assert_seedable(FakeConnection("sqlite")) == "sqlite"


def test_guard_blocks_unexpected_dialects():
    """postgres, mysql, anything: not a target this tool knows how to refuse."""
    with pytest.raises(seed_dev.GuardViolation):
        seed_dev.assert_seedable(FakeConnection("postgresql"))


def test_resolving_a_non_dev_azure_target_is_refused_before_connecting():
    args = seed_dev.build_parser().parse_args(["--database", "slpdb_2"])
    with pytest.raises(seed_dev.GuardViolation):
        seed_dev._resolve_engine(args)


# ---------------------------------------------------------------------------
# provision_dev_db: the guard and the catalog-only rule
# ---------------------------------------------------------------------------


def test_provision_guard_blocks_production():
    with pytest.raises(provision_dev_db.GuardViolation):
        provision_dev_db._assert_dev_database(FakeConnection("mssql", database_name="slpdb_2"))


def test_provision_guard_allows_slpdb_dev():
    connection = FakeConnection("mssql", database_name="slpdb_dev")
    assert provision_dev_db._assert_dev_database(connection) == "slpdb_dev"


def test_every_shipped_catalog_query_is_catalog_only():
    """The queries this tool is allowed to point at prod. All of them."""
    queries = [name for name in dir(provision_dev_db) if name.startswith("Q_")]
    assert len(queries) >= 7, queries
    for name in queries:
        provision_dev_db._assert_catalog_only(getattr(provision_dev_db, name))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM students",
        "SELECT first, last FROM dbo.students",
        "SELECT s.name FROM sys.tables t JOIN dbo.students s ON 1 = 1",
        "SELECT * FROM alembic_version",
        "DROP TABLE dbo.students",
        "UPDATE dbo.students SET first = 'x'",
        "SELECT 1",
    ],
)
def test_catalog_only_rejects_anything_that_touches_a_user_table(sql):
    with pytest.raises(provision_dev_db.CatalogOnlyViolation):
        provision_dev_db._assert_catalog_only(sql)


def _sql_literals(module) -> list:
    """Every non-docstring string literal in *module* that looks like a query."""
    import ast
    import re

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings:
            continue
        text = node.value.strip()
        # `FROM` can be separated by a newline as easily as a space, which is
        # why this is a word-boundary match and not `" FROM " in text`.
        if text.upper().startswith("SELECT") and re.search(r"\bFROM\b", text, re.IGNORECASE):
            found.append(text)
    return found


def test_the_module_contains_no_query_against_a_user_table():
    """A source-level sweep, not just a check of the queries we remembered.

    Every SQL string literal in the module -- whether or not it is one of the
    ``Q_*`` constants -- has to pass the catalog-only rule. This is what makes
    "safe to point at production" a property of the file rather than a property
    of the reviewer's attention.
    """
    literals = _sql_literals(provision_dev_db)
    assert len(literals) >= 7, literals
    for literal in literals:
        provision_dev_db._assert_catalog_only(literal)


def test_provision_never_builds_sql_by_interpolation():
    """No f-string may assemble a query -- that is how a table name sneaks in."""
    import ast

    tree = ast.parse(Path(provision_dev_db.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            rendered = "".join(
                part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            assert not rendered.strip().upper().startswith("SELECT"), rendered


# ---------------------------------------------------------------------------
# provision_dev_db: diff generation (offline, no database)
# ---------------------------------------------------------------------------


def _inventory(database, tables, triggers=None, modules=None, indexes=None):
    return {
        "meta": {"database": database, "server": "test", "generated_utc": "now"},
        "tables": list(tables),
        "columns": {t: [{"name": "id", "type": "int", "nullable": False}] for t in tables},
        "indexes": indexes or {},
        "foreign_keys": {},
        "check_constraints": {},
        "triggers": triggers or {},
        "modules": modules or {},
    }


def test_diff_emits_missing_triggers_and_views_in_dependency_order():
    baseline = _inventory(
        "slpdb_2",
        ["dbo.students"],
        triggers={
            "dbo.trg_students": {
                "name": "trg_students",
                "schema": "dbo",
                "table": "dbo.students",
                "is_disabled": False,
                "is_instead_of": False,
                "definition": "CREATE TRIGGER dbo.trg_students ON dbo.students AFTER UPDATE AS SET NOCOUNT ON;",
            }
        },
        modules={
            "dbo.vw_caseload": {
                "name": "vw_caseload",
                "schema": "dbo",
                "type": "V",
                "definition": "CREATE VIEW dbo.vw_caseload AS SELECT id FROM dbo.students;",
            }
        },
    )
    target = _inventory("slpdb_dev", ["dbo.students"])

    script, summary = provision_dev_db.build_diff(baseline, target)

    assert summary["missing_triggers"] == ["dbo.trg_students"]
    assert summary["missing_modules"] == ["dbo.vw_caseload"]
    # The view has to be created before the trigger that might read it.
    assert script.index("CREATE VIEW") < script.index("CREATE TRIGGER")


def test_diff_reports_schema_drift_but_never_generates_table_ddl():
    baseline = _inventory("slpdb_2", ["dbo.students", "dbo.legacy"])
    target = _inventory("slpdb_dev", ["dbo.students"])

    script, summary = provision_dev_db.build_diff(baseline, target)

    assert summary["missing_tables"] == ["dbo.legacy"]
    assert "CREATE TABLE" not in script
    assert "dbo.legacy" in script  # reported as a comment


def test_diff_of_identical_inventories_produces_no_ddl():
    inventory = _inventory("slpdb_2", ["dbo.students"])
    script, summary = provision_dev_db.build_diff(inventory, inventory)
    assert provision_dev_db.split_batches(script) == []
    assert summary["missing_triggers"] == []


def test_split_batches_honours_go_and_drops_comment_only_batches():
    script = "-- header\nGO\nCREATE VIEW v AS SELECT 1 AS x;\nGO\n-- trailer\n"
    assert provision_dev_db.split_batches(script) == ["CREATE VIEW v AS SELECT 1 AS x;"]


# ---------------------------------------------------------------------------
# seed_dev: the end-to-end sqlite run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    """One seed, shared by the assertions below. Roughly a second."""
    db_path = tmp_path_factory.mktemp("seed") / "seed.db"
    engine = seed_dev.build_sqlite_engine(str(db_path))
    counts = seed_dev.run(engine, do_reset=False, verbose=False)
    return engine, counts


def test_seed_produces_exactly_the_planned_row_counts(seeded):
    _, counts = seeded
    assert counts == seed_dev.PLAN


def test_seed_row_counts_are_what_is_actually_in_the_database(seeded):
    from sqlalchemy.orm import Session

    engine, _ = seeded
    with Session(engine) as session:
        assert seed_dev.count_rows(session) == seed_dev.PLAN


def test_seeded_data_is_referentially_intact(seeded):
    """sqlite's own foreign-key checker, over the whole file."""
    from sqlalchemy import text

    engine, _ = seeded
    with engine.connect() as connection:
        violations = connection.execute(text("PRAGMA foreign_key_check")).fetchall()
    assert violations == []


def test_progress_notes_name_the_student_they_belong_to(seeded):
    """The point of the seeded notes: they read like notes about someone."""
    from sqlalchemy import text

    engine, _ = seeded
    with engine.connect() as connection:
        anonymous = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM objective_progress_entries pe
                JOIN goal_objectives o ON o.id = pe.objective_id
                JOIN iep_goals g ON g.id = o.goal_id
                JOIN students s ON s.id = g.student_id
                WHERE instr(pe.progress_comments, s.first) = 0
                """
            )
        ).scalar_one()
        sample = connection.execute(
            text("SELECT progress_comments FROM objective_progress_entries LIMIT 1")
        ).scalar_one()

    assert anonymous == 0
    assert sample.count(".") >= 3, sample  # sentences, not a fragment


def test_the_dev_user_can_see_every_seeded_student(seeded):
    from sqlalchemy import text

    engine, _ = seeded
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT u.external_auth_id, COUNT(a.id)
                FROM users u
                JOIN user_student_access a ON a.user_id = u.id AND a.is_active = 1
                GROUP BY u.external_auth_id
                """
            )
        ).one()
    assert row[0] == seed_dev.DEV_USER_EXTERNAL_ID
    assert row[1] == seed_dev.PLAN["students"]


def test_seeding_twice_without_reset_is_refused(seeded):
    engine, _ = seeded
    with pytest.raises(SystemExit) as excinfo:
        seed_dev.run(engine, do_reset=False, verbose=False)
    assert "--reset" in str(excinfo.value)


def test_reset_then_reseed_reproduces_the_same_caseload(tmp_path):
    """--reset has to delete in foreign-key order and leave a clean slate."""
    from sqlalchemy.orm import Session

    engine = seed_dev.build_sqlite_engine(str(tmp_path / "reset.db"))
    first = seed_dev.run(engine, do_reset=False, verbose=False)
    second = seed_dev.run(engine, do_reset=True, verbose=False)

    assert second == first == seed_dev.PLAN
    with Session(engine) as session:
        assert seed_dev.count_rows(session) == seed_dev.PLAN


def test_reset_leaves_every_seeded_table_empty(tmp_path):
    from sqlalchemy.orm import Session

    engine = seed_dev.build_sqlite_engine(str(tmp_path / "empty.db"))
    seed_dev.run(engine, do_reset=False, verbose=False)
    with Session(engine) as session:
        seed_dev.reset(session, verbose=False)
        assert set(seed_dev.count_rows(session).values()) == {0}


def test_delete_order_covers_every_table_the_seeder_writes():
    """A table added to PLAN and forgotten in DELETE_ORDER makes --reset lie."""
    assert set(seed_dev.DELETE_ORDER) == set(seed_dev.PLAN)
