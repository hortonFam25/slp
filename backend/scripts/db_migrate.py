"""
Operator-side Alembic runner for SLP Pro's Azure SQL databases — NON-DESTRUCTIVE ONLY.

Why this exists
---------------
The GitHub workflow identity (slp-deploy-github) deliberately has schema-only
rights: it can ALTER tables but cannot read or write a single row. That is the
right posture for an unattended robot, and it is exactly why it fails on two
ordinary kinds of migration:

  * a data backfill (UPDATE ... SET new_column = ...), and
  * adding a FOREIGN KEY to an existing table — SQL Server validates existing
    rows, which needs SELECT on the table.

This script runs those as the human operator's Entra identity (the server
admin, via `az account get-access-token`) — no passwords, no grants, no MFA
round-trips — but ONLY after a static guard proves every pending migration's
upgrade() is additive. Anything that can destroy data (drop_table, drop_column,
drop_index, DELETE, TRUNCATE, DROP) makes it refuse; there is intentionally no
override flag. Destructive migrations need a person at the keyboard.

Usage
-----
  python backend/scripts/db_migrate.py upgrade --target dev
  python backend/scripts/db_migrate.py upgrade --target prod
  python backend/scripts/db_migrate.py current --target prod
  python backend/scripts/db_migrate.py revoke-temp-grants --target prod

`revoke-temp-grants` only ever REMOVES permissions from the workflow identity
(the temporary SELECT/UPDATE grants a backfill migration once needed).
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
import urllib.parse
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = BACKEND_DIR / "app"
VERSIONS_DIR = ALEMBIC_DIR / "alembic" / "versions"
SERVER = "hortonfam.database.windows.net"
TARGETS = {"dev": "slpdb_dev", "prod": "slpdb_2"}
DRIVER = "ODBC Driver 18 for SQL Server"
WORKFLOW_IDENTITY = "slp-deploy-github"

# Anything matching these inside upgrade() means "a person runs this, not me".
DESTRUCTIVE_PATTERNS = [
    r"\bdrop_table\b",
    r"\bdrop_column\b",
    r"\bdrop_index\b",
    r"\bdrop_constraint\b",
    r"\bDROP\s+(TABLE|COLUMN|INDEX|CONSTRAINT)\b",
    r"\bDELETE\s+FROM\b",
    r"\bTRUNCATE\b",
]

TEMP_GRANT_TABLES = [
    "students",
    "iep_goals",
    "goal_objectives",
    "objective_progress_entries",
    "therapy_sessions",
    "appointments",
    "time_blocks",
]


def _token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource", "https://database.windows.net/",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=True, shell=(os.name == "nt"),
    )
    return out.stdout.strip()


def _connect(database: str, token: str):
    import pyodbc

    tb = token.encode("utf-16-le")
    attrs = {1256: struct.pack("<i", len(tb)) + tb}  # SQL_COPT_SS_ACCESS_TOKEN
    return pyodbc.connect(
        f"Driver={{{DRIVER}}};Server=tcp:{SERVER},1433;Database={database};Encrypt=yes",
        attrs_before=attrs,
    )


def _current_revision(database: str, token: str) -> str | None:
    cn = _connect(database, token)
    try:
        cur = cn.cursor()
        cur.execute("SELECT DB_NAME()")
        actual = cur.fetchone()[0]
        if actual != database:
            raise SystemExit(f"refusing: connected to {actual!r}, expected {database!r}")
        cur.execute("SELECT COUNT(*) FROM sys.tables WHERE name = 'alembic_version'")
        if not cur.fetchone()[0]:
            return None
        cur.execute("SELECT version_num FROM alembic_version")
        rows = cur.fetchall()
        return rows[0][0] if rows else None
    finally:
        cn.close()


def _pending_revisions(current: str | None) -> list:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(ALEMBIC_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    lower = current or "base"
    # iterate_revisions walks head -> lower (exclusive of lower)
    return list(script.iterate_revisions("head", lower))


def _upgrade_body(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    if "def upgrade(" not in src:
        return ""
    body = src.split("def upgrade(", 1)[1]
    body = body.split("def downgrade(", 1)[0]
    # strip comments and docstring-ish lines so prose can't trip the guard
    lines = [ln for ln in body.splitlines() if not ln.strip().startswith("#")]
    return "\n".join(lines)


def guard(pending) -> None:
    bad = []
    for rev in pending:
        body = _upgrade_body(Path(rev.path))
        hits = [p for p in DESTRUCTIVE_PATTERNS if re.search(p, body, re.IGNORECASE)]
        if hits:
            bad.append((rev.revision, Path(rev.path).name, hits))
    if bad:
        print("REFUSING: destructive operations in pending migrations:")
        for revision, name, hits in bad:
            print(f"  {revision} {name}: {hits}")
        print("Destructive migrations must be run by a human operator, by design.")
        raise SystemExit(2)


def _alembic(command: list[str], database: str, token: str) -> int:
    odbc = (
        f"DRIVER={{{DRIVER}}};SERVER=tcp:{SERVER},1433;DATABASE={database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )
    env = dict(os.environ)
    env["SLP_DB_ACCESS_TOKEN"] = token
    env["SQL_SERVER_CONNECTION_STRING"] = (
        "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc)
    )
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *command],
        cwd=str(ALEMBIC_DIR), env=env, check=False,
    ).returncode


def cmd_current(database: str, token: str) -> int:
    print(f"{database}: {_current_revision(database, token)}")
    return 0


def cmd_upgrade(database: str, token: str) -> int:
    current = _current_revision(database, token)
    pending = _pending_revisions(current)
    print(f"{database} is at {current}; {len(pending)} pending migration(s)")
    if not pending:
        print("nothing to do")
        return 0
    for rev in reversed(pending):
        print(f"  {rev.revision}  {Path(rev.path).name}")
    guard(pending)
    print("guard: all pending migrations are non-destructive")
    rc = _alembic(["upgrade", "head"], database, token)
    print(f"{database} now at {_current_revision(database, token)}")
    return rc


def cmd_revoke_temp_grants(database: str, token: str) -> int:
    cn = _connect(database, token)
    try:
        cur = cn.cursor()
        for table in TEMP_GRANT_TABLES:
            cur.execute(
                f"REVOKE SELECT, UPDATE ON OBJECT::dbo.{table} FROM [{WORKFLOW_IDENTITY}]"
            )
        cn.commit()
        cur.execute(
            "SELECT COUNT(*) FROM sys.database_permissions p "
            "JOIN sys.database_principals u ON u.principal_id = p.grantee_principal_id "
            "WHERE u.name = ? AND p.class = 1 AND p.permission_name IN ('SELECT','UPDATE') "
            "AND OBJECT_NAME(p.major_id) <> 'alembic_version'",
            WORKFLOW_IDENTITY,
        )
        leftover = cur.fetchone()[0]
        print(f"{database}: revoked temp grants; remaining table-level SELECT/UPDATE "
              f"for {WORKFLOW_IDENTITY} outside alembic_version: {leftover}")
        return 0 if leftover == 0 else 1
    finally:
        cn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["upgrade", "current", "revoke-temp-grants"])
    ap.add_argument("--target", choices=sorted(TARGETS), required=True)
    args = ap.parse_args()
    database = TARGETS[args.target]
    token = _token()
    return {
        "upgrade": cmd_upgrade,
        "current": cmd_current,
        "revoke-temp-grants": cmd_revoke_temp_grants,
    }[args.command](database, token)


if __name__ == "__main__":
    raise SystemExit(main())
