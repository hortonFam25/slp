#!/usr/bin/env python3
"""Provision, inventory and reconcile the SLP Pro databases.

This script has four modes. Only ONE of them can write, and it can only write
to a database literally named ``slpdb_dev``:

  ``--provision``   create every table in ``app.models`` and ``alembic stamp head``.
                    HARD GUARDED: refuses unless ``DB_NAME() = 'slpdb_dev'``.

  ``--compare``     dump a CATALOG-ONLY schema inventory to JSON. Safe to point
                    at ANY database, production included: every statement it
                    issues is a ``SELECT`` against ``sys.*`` /
                    ``INFORMATION_SCHEMA.*`` and is checked to be so at runtime
                    (see ``_assert_catalog_only``). It never reads a user table,
                    so it never sees a student, a goal, or a note.

  ``--diff``        compare two ``--compare`` JSON files offline (no database
                    connection at all) and emit the DDL for objects that the
                    baseline has and the target is missing -- triggers, views,
                    functions, procedures, and secondary indexes.

  ``--apply``       run a ``--diff`` DDL file against the target.
                    HARD GUARDED: refuses unless ``DB_NAME() = 'slpdb_dev'``.

Why the guard is structural, not just a flag
--------------------------------------------
Two functions in this module can put a statement on the wire:

  ``_run_catalog_query``  SELECT only, and only against ``sys.*`` /
                          ``INFORMATION_SCHEMA.*``. Enforced per statement.
  ``_execute_ddl``        anything else. Its FIRST line calls
                          ``_assert_dev_database``, which raises unless the
                          server answers ``slpdb_dev`` to ``SELECT DB_NAME()``.

``--provision`` and ``--apply`` are the only callers of ``_execute_ddl`` and
both re-assert the guard on the connection they are about to use. The name is
taken from the SERVER's answer, never from the caller's argument, so a typo, a
stale environment variable, or a redirected DNS name cannot get past it.

Connecting
----------
Entra ID (Azure AD) tokens only -- there are no SQL passwords for these servers.

  ``SLP_DB_AUTH=token``  (default) ``az account get-access-token --resource
                         https://database.windows.net/`` and hand the result to
                         the ODBC driver as ``SQL_COPT_SS_ACCESS_TOKEN`` (1256).
  ``SLP_DB_AUTH=azcli``  let ODBC Driver 18 do the same thing itself via
                         ``Authentication=ActiveDirectoryAzCli``.

Environment
-----------
  ``SLP_DB_SERVER``  default ``hortonfam.database.windows.net``
  ``SLP_DB_NAME``    REQUIRED for every mode that connects
  ``SLP_ODBC_DRIVER``  default ``ODBC Driver 18 for SQL Server``
  ``SLP_DB_AUTH``    ``token`` (default) or ``azcli``

``--provision`` sets ``SQL_SERVER_CONNECTION_STRING`` for the ``alembic stamp``
subprocess, which is the same variable ``app/alembic/env.py`` reads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

#: The ONLY database name this script will ever write to. Not configurable on
#: purpose -- making it an argument is how a dev tool ends up pointed at prod.
ALLOWED_WRITE_DB_NAME = "slpdb_dev"

DEFAULT_SERVER = "hortonfam.database.windows.net"
DEFAULT_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"

#: SQL_COPT_SS_ACCESS_TOKEN -- the pre-connect attribute the Microsoft ODBC
#: driver reads an Entra access token from.
SQL_COPT_SS_ACCESS_TOKEN = 1256

#: The audience an Azure SQL access token has to be minted for.
AZURE_SQL_TOKEN_RESOURCE = "https://database.windows.net/"

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = BACKEND_DIR / "app"

#: The revision prod's pre-alembic schema corresponds to. Kept here so the
#: bootstrap value lives next to the code that talks about it; the workflow
#: (.github/workflows/migrate.yml) carries the same constant.
PRE_ALEMBIC_BASELINE_REVISION = "f2d4b8c9a1e0"

INVENTORY_FORMAT_VERSION = 1


class GuardViolation(RuntimeError):
    """Raised when a write was attempted against something that is not dev."""


class CatalogOnlyViolation(RuntimeError):
    """Raised when a read-only mode was handed SQL that touches a user table."""


# ---------------------------------------------------------------------------
# catalog-only enforcement
# ---------------------------------------------------------------------------

_SOURCE_RE = re.compile(r"\b(?:FROM|JOIN|APPLY|INTO|UPDATE)\s+([A-Za-z_\[][\w.\[\]]*)", re.IGNORECASE)
_ALLOWED_SOURCE_PREFIXES = ("sys.", "information_schema.")


def _normalise_source(raw: str) -> str:
    return raw.replace("[", "").replace("]", "").lower()


def _assert_catalog_only(sql: str) -> None:
    """Fail unless *sql* is a single SELECT that reads only system catalogs.

    This is the mechanical half of the "prod is PII, never touch it" rule. A
    human reading the queries below can see they are catalog views; this makes
    that a property the program checks rather than a property a reviewer
    remembered to check.
    """
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        raise CatalogOnlyViolation(f"catalog reads must start with SELECT, got: {stripped[:60]!r}")
    if ";" in stripped.rstrip(";"):
        raise CatalogOnlyViolation("catalog reads must be a single statement")
    sources = [_normalise_source(m.group(1)) for m in _SOURCE_RE.finditer(stripped)]
    if not sources:
        raise CatalogOnlyViolation("could not identify any FROM/JOIN source to validate")
    for source in sources:
        if not source.startswith(_ALLOWED_SOURCE_PREFIXES):
            raise CatalogOnlyViolation(
                f"{source!r} is not a system catalog view. This script may only read "
                f"sys.* / INFORMATION_SCHEMA.* -- user tables hold student PII."
            )


# ---------------------------------------------------------------------------
# the catalog queries
# ---------------------------------------------------------------------------
# Every one of these is validated by _assert_catalog_only() before it is sent.

Q_TABLES = """
SELECT s.name AS [schema_name], t.name AS [table_name]
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name
"""

Q_COLUMNS = """
SELECT s.name AS [schema_name], t.name AS [table_name], c.name AS [column_name],
       c.column_id, ty.name AS [type_name], c.max_length, c.precision, c.scale,
       c.is_nullable, c.is_identity, c.is_computed, c.collation_name,
       cc.definition AS [computed_definition],
       dc.name AS [default_name], dc.definition AS [default_definition]
FROM sys.columns c
JOIN sys.tables t ON t.object_id = c.object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.types ty ON ty.user_type_id = c.user_type_id
LEFT JOIN sys.computed_columns cc ON cc.object_id = c.object_id AND cc.column_id = c.column_id
LEFT JOIN sys.default_constraints dc ON dc.object_id = c.default_object_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id
"""

Q_INDEXES = """
SELECT s.name AS [schema_name], t.name AS [table_name], i.name AS [index_name],
       i.type_desc, i.is_unique, i.is_primary_key, i.is_unique_constraint,
       i.filter_definition, c.name AS [column_name], ic.key_ordinal,
       ic.index_column_id, ic.is_descending_key, ic.is_included_column
FROM sys.indexes i
JOIN sys.tables t ON t.object_id = i.object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE t.is_ms_shipped = 0 AND i.type <> 0 AND i.name IS NOT NULL
ORDER BY s.name, t.name, i.name, ic.is_included_column, ic.key_ordinal, ic.index_column_id
"""

Q_FOREIGN_KEYS = """
SELECT s.name AS [schema_name], t.name AS [table_name], fk.name AS [fk_name],
       rs.name AS [ref_schema_name], rt.name AS [ref_table_name],
       pc.name AS [column_name], rc.name AS [ref_column_name],
       fk.delete_referential_action_desc, fk.update_referential_action_desc,
       fkc.constraint_column_id
FROM sys.foreign_keys fk
JOIN sys.tables t ON t.object_id = fk.parent_object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
ORDER BY s.name, t.name, fk.name, fkc.constraint_column_id
"""

Q_CHECK_CONSTRAINTS = """
SELECT s.name AS [schema_name], t.name AS [table_name], cc.name AS [check_name],
       cc.definition, cc.is_disabled
FROM sys.check_constraints cc
JOIN sys.tables t ON t.object_id = cc.parent_object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
ORDER BY s.name, t.name, cc.name
"""

Q_TRIGGERS = """
SELECT s.name AS [schema_name], t.name AS [table_name], tr.name AS [trigger_name],
       tr.is_disabled, tr.is_instead_of_trigger, m.definition
FROM sys.triggers tr
JOIN sys.tables t ON t.object_id = tr.parent_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
LEFT JOIN sys.sql_modules m ON m.object_id = tr.object_id
WHERE tr.is_ms_shipped = 0 AND tr.parent_class = 1
ORDER BY s.name, t.name, tr.name
"""

Q_MODULES = """
SELECT s.name AS [schema_name], o.name AS [object_name], o.type AS [object_type],
       m.definition
FROM sys.objects o
JOIN sys.schemas s ON s.schema_id = o.schema_id
LEFT JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.is_ms_shipped = 0 AND o.type IN ('V', 'P', 'FN', 'IF', 'TF')
ORDER BY o.type, s.name, o.name
"""

Q_DB_NAME = "SELECT DB_NAME() AS [database_name] FROM sys.databases WHERE database_id = DB_ID()"

#: Object types sys.sql_modules definitions are replayed for, in dependency
#: order: views before the functions/procedures that may select from them,
#: everything before triggers.
MODULE_EMIT_ORDER = ("V", "FN", "IF", "TF", "P")
MODULE_TYPE_LABELS = {
    "V": "view",
    "FN": "scalar function",
    "IF": "inline table-valued function",
    "TF": "table-valued function",
    "P": "stored procedure",
}


# ---------------------------------------------------------------------------
# connecting
# ---------------------------------------------------------------------------


def _az_executable() -> str:
    az = shutil.which("az")
    if not az:
        raise RuntimeError(
            "the Azure CLI ('az') is not on PATH. It is how this script gets an "
            "Entra token for Azure SQL -- there is no password fallback."
        )
    return az


def fetch_access_token(resource: str = AZURE_SQL_TOKEN_RESOURCE) -> str:
    """Mint an Azure SQL access token for whoever `az` is currently logged in as.

    The token is returned, never logged. Callers must not print it.
    """
    command = [
        _az_executable(), "account", "get-access-token",
        "--resource", resource,
        "--query", "accessToken", "-o", "tsv",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # stderr from `az` is safe to show -- it is a login/tenant diagnostic and
        # carries no token material.
        raise RuntimeError(f"az account get-access-token failed:\n{result.stderr.strip()}")
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("az returned an empty access token")
    return token


def _token_struct(token: str) -> bytes:
    """Pack a bearer token the way SQL_COPT_SS_ACCESS_TOKEN wants it.

    4-byte little-endian length followed by the token in UTF-16-LE.
    """
    encoded = token.encode("utf-16-le")
    return struct.pack("<i", len(encoded)) + encoded


def odbc_connection_string(server: str, database: str, driver: str, use_azcli: bool) -> str:
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER=tcp:{server},1433",
        f"DATABASE={database}",
        "Encrypt=yes",
        "TrustServerCertificate=no",
        "Connection Timeout=60",
    ]
    if use_azcli:
        parts.append("Authentication=ActiveDirectoryAzCli")
    return ";".join(parts) + ";"


def sqlalchemy_url(odbc: str) -> str:
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


def build_engine(server: str, database: str, *, driver: str, auth: str):
    """An engine for one Azure SQL database. Import-light: SQLAlchemy only here."""
    from sqlalchemy import create_engine

    use_azcli = auth == "azcli"
    odbc = odbc_connection_string(server, database, driver, use_azcli)
    connect_args: Dict[str, Any] = {}
    if not use_azcli:
        connect_args["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: _token_struct(fetch_access_token())}

    with warnings.catch_warnings():
        # implicit_returning=False is deprecated in SQLAlchemy 2.0 but is still
        # the switch that stops the MSSQL dialect emitting an OUTPUT clause,
        # which SQL Server rejects on any table carrying a trigger. The app
        # (app/db/database.py) sets it for the same reason.
        warnings.simplefilter("ignore")
        return create_engine(
            sqlalchemy_url(odbc),
            implicit_returning=False,
            use_insertmanyvalues=False,
            connect_args=connect_args,
            pool_pre_ping=True,
        )


# ---------------------------------------------------------------------------
# the two statement gateways
# ---------------------------------------------------------------------------


def _run_catalog_query(connection, sql: str) -> List[Dict[str, Any]]:
    """The ONLY read path. Validates the statement, then returns dict rows."""
    from sqlalchemy import text

    _assert_catalog_only(sql)
    result = connection.execute(text(sql))
    columns = list(result.keys())
    return [dict(zip(columns, row)) for row in result.fetchall()]


def current_database_name(connection) -> str:
    rows = _run_catalog_query(connection, Q_DB_NAME)
    if not rows:
        raise RuntimeError("could not determine the current database name")
    return str(rows[0]["database_name"])


def _assert_dev_database(connection) -> str:
    """THE guard. Ask the SERVER what database this is; refuse anything else."""
    name = current_database_name(connection)
    if name != ALLOWED_WRITE_DB_NAME:
        raise GuardViolation(
            f"refusing to write: connected to {name!r}, and this script only "
            f"writes to {ALLOWED_WRITE_DB_NAME!r}."
        )
    return name


def _execute_ddl(connection, statements: Sequence[str]) -> int:
    """The ONLY write path. Guarded on the very connection it will use."""
    from sqlalchemy import text

    _assert_dev_database(connection)
    executed = 0
    for statement in statements:
        if not statement.strip():
            continue
        connection.execute(text(statement))
        executed += 1
    return executed


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------


def _qualify(row: Dict[str, Any], schema_key: str = "schema_name", name_key: str = "table_name") -> str:
    return f"{row[schema_key]}.{row[name_key]}"


def _render_type(row: Dict[str, Any]) -> str:
    """`nvarchar(100)`, `decimal(5,2)`, `int` -- the shape a human compares."""
    name = str(row["type_name"]).lower()
    max_length = row["max_length"]
    precision = row["precision"]
    scale = row["scale"]

    if name in ("varchar", "char", "varbinary", "binary"):
        length = "max" if max_length == -1 else str(max_length)
        return f"{name}({length})"
    if name in ("nvarchar", "nchar"):
        length = "max" if max_length == -1 else str(int(max_length) // 2)
        return f"{name}({length})"
    if name in ("decimal", "numeric"):
        return f"{name}({precision},{scale})"
    if name in ("datetime2", "datetimeoffset", "time"):
        return f"{name}({scale})"
    if name in ("float",):
        return f"{name}({precision})"
    return name


def collect_inventory(connection, *, server: str) -> Dict[str, Any]:
    """A catalog-only picture of one database. No user table is read."""
    database = current_database_name(connection)

    tables = [_qualify(r) for r in _run_catalog_query(connection, Q_TABLES)]

    columns: Dict[str, List[Dict[str, Any]]] = {}
    for row in _run_catalog_query(connection, Q_COLUMNS):
        columns.setdefault(_qualify(row), []).append(
            {
                "name": row["column_name"],
                "ordinal": int(row["column_id"]),
                "type": _render_type(row),
                "nullable": bool(row["is_nullable"]),
                "identity": bool(row["is_identity"]),
                "computed": bool(row["is_computed"]),
                "computed_definition": row["computed_definition"],
                "collation": row["collation_name"],
                "default_name": row["default_name"],
                "default_definition": row["default_definition"],
            }
        )

    indexes: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in _run_catalog_query(connection, Q_INDEXES):
        table = _qualify(row)
        entry = indexes.setdefault(table, {}).setdefault(
            str(row["index_name"]),
            {
                "name": row["index_name"],
                "type": row["type_desc"],
                "is_unique": bool(row["is_unique"]),
                "is_primary_key": bool(row["is_primary_key"]),
                "is_unique_constraint": bool(row["is_unique_constraint"]),
                "filter": row["filter_definition"],
                "key_columns": [],
                "included_columns": [],
            },
        )
        if row["is_included_column"]:
            entry["included_columns"].append(row["column_name"])
        else:
            entry["key_columns"].append(
                {"name": row["column_name"], "descending": bool(row["is_descending_key"])}
            )

    foreign_keys: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in _run_catalog_query(connection, Q_FOREIGN_KEYS):
        table = _qualify(row)
        entry = foreign_keys.setdefault(table, {}).setdefault(
            str(row["fk_name"]),
            {
                "name": row["fk_name"],
                "references": f"{row['ref_schema_name']}.{row['ref_table_name']}",
                "on_delete": row["delete_referential_action_desc"],
                "on_update": row["update_referential_action_desc"],
                "columns": [],
            },
        )
        entry["columns"].append({"column": row["column_name"], "references": row["ref_column_name"]})

    check_constraints: Dict[str, List[Dict[str, Any]]] = {}
    for row in _run_catalog_query(connection, Q_CHECK_CONSTRAINTS):
        check_constraints.setdefault(_qualify(row), []).append(
            {
                "name": row["check_name"],
                "definition": row["definition"],
                "is_disabled": bool(row["is_disabled"]),
            }
        )

    triggers: Dict[str, Dict[str, Any]] = {}
    for row in _run_catalog_query(connection, Q_TRIGGERS):
        key = f"{row['schema_name']}.{row['trigger_name']}"
        triggers[key] = {
            "name": row["trigger_name"],
            "schema": row["schema_name"],
            "table": _qualify(row),
            "is_disabled": bool(row["is_disabled"]),
            "is_instead_of": bool(row["is_instead_of_trigger"]),
            "definition": row["definition"],
        }

    modules: Dict[str, Dict[str, Any]] = {}
    for row in _run_catalog_query(connection, Q_MODULES):
        key = f"{row['schema_name']}.{row['object_name']}"
        modules[key] = {
            "name": row["object_name"],
            "schema": row["schema_name"],
            "type": str(row["object_type"]).strip(),
            "definition": row["definition"],
        }

    return {
        "meta": {
            "format_version": INVENTORY_FORMAT_VERSION,
            "server": server,
            "database": database,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            # Whether the table EXISTS, from sys.tables. Its CONTENTS are not
            # read -- that would be a user table, and the rule is catalog only.
            "has_alembic_version": any(t.split(".", 1)[-1] == "alembic_version" for t in tables),
            "table_count": len(tables),
        },
        "tables": sorted(tables),
        "columns": {k: v for k, v in sorted(columns.items())},
        "indexes": {k: dict(sorted(v.items())) for k, v in sorted(indexes.items())},
        "foreign_keys": {k: dict(sorted(v.items())) for k, v in sorted(foreign_keys.items())},
        "check_constraints": {k: v for k, v in sorted(check_constraints.items())},
        "triggers": dict(sorted(triggers.items())),
        "modules": dict(sorted(modules.items())),
    }


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def _bracket(identifier: str) -> str:
    return "[" + str(identifier).replace("]", "]]") + "]"


def _bracket_qualified(qualified: str) -> str:
    schema, _, name = qualified.partition(".")
    return f"{_bracket(schema)}.{_bracket(name)}"


def _create_index_ddl(table: str, index: Dict[str, Any]) -> str:
    unique = "UNIQUE " if index["is_unique"] else ""
    clustered = "CLUSTERED " if str(index.get("type", "")).upper().startswith("CLUSTERED") else "NONCLUSTERED "
    keys = ", ".join(
        f"{_bracket(col['name'])}{' DESC' if col['descending'] else ' ASC'}" for col in index["key_columns"]
    )
    ddl = (
        f"CREATE {unique}{clustered}INDEX {_bracket(index['name'])} "
        f"ON {_bracket_qualified(table)} ({keys})"
    )
    if index.get("included_columns"):
        ddl += " INCLUDE (" + ", ".join(_bracket(c) for c in index["included_columns"]) + ")"
    if index.get("filter"):
        ddl += f" WHERE {index['filter']}"
    return ddl + ";"


def _warn_block(title: str, lines: Iterable[str]) -> List[str]:
    lines = list(lines)
    if not lines:
        return []
    out = ["", f"-- {'=' * 70}", f"-- WARNING: {title}", f"-- {'=' * 70}"]
    out.extend(f"--   {line}" for line in lines)
    return out


def build_diff(baseline: Dict[str, Any], target: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """DDL for what *baseline* has and *target* is missing, plus a summary.

    Schema drift that alembic owns (missing tables, missing/retyped columns) is
    reported as a comment rather than generated: a migration is the right place
    to fix that, and silently CREATE-ing a table here would put the two
    databases further apart, not closer.
    """
    lines: List[str] = []
    summary: Dict[str, Any] = {}

    base_meta = baseline.get("meta", {})
    tgt_meta = target.get("meta", {})
    lines.append("-- Generated by backend/scripts/provision_dev_db.py --diff")
    lines.append(f"-- baseline : {base_meta.get('database')} on {base_meta.get('server')} "
                 f"({base_meta.get('generated_utc')})")
    lines.append(f"-- target   : {tgt_meta.get('database')} on {tgt_meta.get('server')} "
                 f"({tgt_meta.get('generated_utc')})")
    lines.append("--")
    lines.append("-- Apply with:  python backend/scripts/provision_dev_db.py --apply <this file>")
    lines.append(f"-- (that mode refuses to run against anything but {ALLOWED_WRITE_DB_NAME})")

    # --- tables / columns: reported, never generated ------------------------
    base_tables = set(baseline.get("tables", []))
    tgt_tables = set(target.get("tables", []))
    missing_tables = sorted(base_tables - tgt_tables)
    extra_tables = sorted(tgt_tables - base_tables)
    summary["missing_tables"] = missing_tables
    summary["extra_tables"] = extra_tables
    lines.extend(
        _warn_block(
            "tables present in the baseline and MISSING from the target",
            missing_tables or [],
        )
    )
    lines.extend(
        _warn_block(
            "tables present in the target only (expected: alembic_version, dev scratch)",
            extra_tables or [],
        )
    )

    missing_columns: List[str] = []
    changed_columns: List[str] = []
    for table in sorted(base_tables & tgt_tables):
        base_cols = {c["name"]: c for c in baseline.get("columns", {}).get(table, [])}
        tgt_cols = {c["name"]: c for c in target.get("columns", {}).get(table, [])}
        for name, col in base_cols.items():
            if name not in tgt_cols:
                missing_columns.append(f"{table}.{name} ({col['type']}, "
                                       f"{'NULL' if col['nullable'] else 'NOT NULL'})")
                continue
            other = tgt_cols[name]
            if (col["type"], col["nullable"]) != (other["type"], other["nullable"]):
                changed_columns.append(
                    f"{table}.{name}: baseline {col['type']} "
                    f"{'NULL' if col['nullable'] else 'NOT NULL'} != target "
                    f"{other['type']} {'NULL' if other['nullable'] else 'NOT NULL'}"
                )
    summary["missing_columns"] = missing_columns
    summary["changed_columns"] = changed_columns
    lines.extend(_warn_block("columns MISSING from the target -- fix with a migration, not here", missing_columns))
    lines.extend(_warn_block("columns whose type/nullability DIFFERS -- fix with a migration", changed_columns))

    # --- indexes ------------------------------------------------------------
    index_ddl: List[str] = []
    for table in sorted(base_tables & tgt_tables):
        base_idx = baseline.get("indexes", {}).get(table, {})
        tgt_idx = target.get("indexes", {}).get(table, {})
        for name, index in sorted(base_idx.items()):
            if name in tgt_idx:
                continue
            # PK and UNIQUE-constraint indexes are table DDL, not standalone
            # objects: they arrive with create_all / a migration.
            if index.get("is_primary_key") or index.get("is_unique_constraint"):
                continue
            if not index.get("key_columns"):
                continue
            index_ddl.append(_create_index_ddl(table, index))
    summary["missing_indexes"] = len(index_ddl)
    if index_ddl:
        lines.append("")
        lines.append(f"-- {'=' * 70}")
        lines.append(f"-- {len(index_ddl)} missing index(es)")
        lines.append(f"-- {'=' * 70}")
        for ddl in index_ddl:
            lines.append(ddl)
            lines.append("GO")

    # --- modules (views, functions, procedures) -----------------------------
    base_modules = baseline.get("modules", {})
    tgt_modules = target.get("modules", {})
    emitted_modules: List[str] = []
    unavailable: List[str] = []
    for object_type in MODULE_EMIT_ORDER:
        for key, module in sorted(base_modules.items()):
            if module.get("type") != object_type or key in tgt_modules:
                continue
            definition = module.get("definition")
            if not definition:
                unavailable.append(f"{key} ({MODULE_TYPE_LABELS.get(object_type, object_type)}) "
                                   f"-- no definition in sys.sql_modules (encrypted?)")
                continue
            emitted_modules.append(key)
            lines.append("")
            lines.append(f"-- {'-' * 70}")
            lines.append(f"-- {MODULE_TYPE_LABELS.get(object_type, object_type)}: {key}")
            lines.append(f"-- {'-' * 70}")
            lines.append(definition.rstrip())
            lines.append("GO")
    summary["missing_modules"] = emitted_modules

    # --- triggers (last: they need their tables and any view they read) -----
    base_triggers = baseline.get("triggers", {})
    tgt_triggers = target.get("triggers", {})
    emitted_triggers: List[str] = []
    for key, trigger in sorted(base_triggers.items()):
        if key in tgt_triggers:
            continue
        if trigger["table"] not in tgt_tables:
            unavailable.append(f"{key} -- its table {trigger['table']} does not exist on the target")
            continue
        definition = trigger.get("definition")
        if not definition:
            unavailable.append(f"{key} (trigger) -- no definition in sys.sql_modules (encrypted?)")
            continue
        emitted_triggers.append(key)
        lines.append("")
        lines.append(f"-- {'-' * 70}")
        lines.append(f"-- trigger: {key} on {trigger['table']}")
        lines.append(f"-- {'-' * 70}")
        lines.append(definition.rstrip())
        lines.append("GO")
        if trigger.get("is_disabled"):
            lines.append(f"DISABLE TRIGGER {_bracket_qualified(key)} ON {_bracket_qualified(trigger['table'])};")
            lines.append("GO")
    summary["missing_triggers"] = emitted_triggers

    lines.extend(_warn_block("objects that could NOT be scripted", unavailable))
    summary["unavailable"] = unavailable

    if not index_ddl and not emitted_modules and not emitted_triggers:
        lines.append("")
        lines.append("-- Nothing to apply: the target already has every trigger, view,")
        lines.append("-- function, procedure and secondary index the baseline has.")

    return "\n".join(lines) + "\n", summary


def split_batches(script: str) -> List[str]:
    """Split a T-SQL script on its GO batch separators.

    GO is a client directive, not a statement -- pyodbc cannot send it, and
    CREATE TRIGGER / CREATE VIEW have to be the first statement in their batch.
    """
    batches: List[str] = []
    current: List[str] = []
    for line in script.splitlines():
        if re.fullmatch(r"\s*GO\s*;?\s*", line, re.IGNORECASE):
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))

    cleaned = []
    for batch in batches:
        # A batch of nothing but comments and blank lines has nothing to send.
        meaningful = [ln for ln in batch.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if meaningful:
            cleaned.append(batch.strip())
    return cleaned


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------


def _resolve_target(args: argparse.Namespace) -> Tuple[str, str]:
    server = args.server or os.environ.get("SLP_DB_SERVER") or DEFAULT_SERVER
    database = args.database or os.environ.get("SLP_DB_NAME") or ""
    if not database:
        raise SystemExit("SLP_DB_NAME (or --database) is required -- refusing to guess a database name.")
    return server, database


def mode_provision(args: argparse.Namespace) -> int:
    server, database = _resolve_target(args)

    # Belt as well as braces: the SERVER's answer is the guard that matters
    # (_assert_dev_database), but there is no reason to open a connection to
    # something we already know we will refuse.
    if database != ALLOWED_WRITE_DB_NAME:
        raise GuardViolation(
            f"--provision only ever targets {ALLOWED_WRITE_DB_NAME!r}; SLP_DB_NAME is {database!r}."
        )

    sys.path.insert(0, str(BACKEND_DIR))
    from app.db.base import Base
    import app.models  # noqa: F401  (registers all 31 tables on Base.metadata)

    engine = build_engine(server, database, driver=args.driver, auth=args.auth)
    with engine.begin() as connection:
        name = _assert_dev_database(connection)
        print(f"connected to {name} on {server} -- guard satisfied")
        before = {f"{r['schema_name']}.{r['table_name']}" for r in _run_catalog_query(connection, Q_TABLES)}

    print(f"{len(before)} table(s) already present")
    print(f"creating {len(Base.metadata.tables)} table(s) from app.models ...")
    Base.metadata.create_all(engine)

    with engine.connect() as connection:
        _assert_dev_database(connection)
        after = [f"{r['schema_name']}.{r['table_name']}" for r in _run_catalog_query(connection, Q_TABLES)]
    created = sorted(set(after) - before)
    print(f"{len(after)} table(s) now present ({len(created)} created)")
    for table in created:
        print(f"  + {table}")

    if args.skip_stamp:
        print("--skip-stamp: not stamping alembic")
        return 0

    return _alembic(["stamp", "head"], server, database, args)


def _alembic(command: List[str], server: str, database: str, args: argparse.Namespace) -> int:
    """Shell out to alembic with the connection string env.py reads.

    app/alembic.ini says `script_location = alembic`, a RELATIVE path, so
    alembic has to be invoked with backend/app as the working directory. That
    is not a preference -- from anywhere else it cannot find the versions/
    directory at all.
    """
    odbc = odbc_connection_string(
        server, database, args.driver, use_azcli=True
    )
    env = dict(os.environ)
    # ActiveDirectoryAzCli rather than a token struct: env.py builds its engine
    # with engine_from_config() and has no way to take connect_args, and a URL
    # is the only channel we have. The driver mints the same token from the
    # same `az` login; nothing secret ends up in the environment.
    env["SQL_SERVER_CONNECTION_STRING"] = sqlalchemy_url(odbc)
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    print(f"$ alembic -c alembic.ini {' '.join(command)}   (cwd={ALEMBIC_DIR})")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *command],
        cwd=str(ALEMBIC_DIR),
        env=env,
        check=False,
    )
    return result.returncode


def mode_compare(args: argparse.Namespace) -> int:
    server, database = _resolve_target(args)
    engine = build_engine(server, database, driver=args.driver, auth=args.auth)
    with engine.connect() as connection:
        inventory = collect_inventory(connection, server=server)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2, sort_keys=False, default=str), encoding="utf-8")

    meta = inventory["meta"]
    print(f"catalog inventory of {meta['database']} on {meta['server']}")
    print(f"  tables           : {len(inventory['tables'])}")
    print(f"  triggers         : {len(inventory['triggers'])}")
    print(f"  views/procs/funcs: {len(inventory['modules'])}")
    print(f"  alembic_version  : {'present' if meta['has_alembic_version'] else 'ABSENT'}")
    print(f"  written to       : {out}")
    return 0


def mode_diff(args: argparse.Namespace) -> int:
    baseline = json.loads(Path(args.diff[0]).read_text(encoding="utf-8"))
    target = json.loads(Path(args.diff[1]).read_text(encoding="utf-8"))
    script, summary = build_diff(baseline, target)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(script, encoding="utf-8")

    print(f"diff {baseline['meta'].get('database')} -> {target['meta'].get('database')}")
    print(f"  tables missing from target : {len(summary['missing_tables'])}")
    print(f"  columns missing from target: {len(summary['missing_columns'])}")
    print(f"  columns that differ        : {len(summary['changed_columns'])}")
    print(f"  indexes to create          : {summary['missing_indexes']}")
    print(f"  views/procs/funcs to create: {len(summary['missing_modules'])}")
    print(f"  triggers to create         : {len(summary['missing_triggers'])}")
    print(f"  could not be scripted      : {len(summary['unavailable'])}")
    print(f"  written to                 : {out}")
    return 0


def mode_apply(args: argparse.Namespace) -> int:
    server, database = _resolve_target(args)
    if database != ALLOWED_WRITE_DB_NAME:
        raise GuardViolation(
            f"--apply only ever targets {ALLOWED_WRITE_DB_NAME!r}; SLP_DB_NAME is {database!r}."
        )

    script = Path(args.apply).read_text(encoding="utf-8")
    batches = split_batches(script)
    if not batches:
        print("nothing to apply -- the DDL file has no executable batches")
        return 0

    engine = build_engine(server, database, driver=args.driver, auth=args.auth)
    with engine.begin() as connection:
        name = _assert_dev_database(connection)
        print(f"connected to {name} on {server} -- guard satisfied")
        if args.dry_run:
            print(f"--dry-run: {len(batches)} batch(es) would be executed")
            for i, batch in enumerate(batches, 1):
                print(f"  [{i}] {batch.splitlines()[0][:100]}")
            return 0
        executed = _execute_ddl(connection, batches)
    print(f"applied {executed} batch(es) to {database}")
    return 0


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provision_dev_db.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--provision",
        action="store_true",
        help=f"create_all + alembic stamp head. Only ever against {ALLOWED_WRITE_DB_NAME}.",
    )
    mode.add_argument(
        "--compare",
        action="store_true",
        help="dump a catalog-only schema inventory as JSON (read-only, safe against prod)",
    )
    mode.add_argument(
        "--diff",
        nargs=2,
        metavar=("BASELINE.json", "TARGET.json"),
        help="offline: emit the DDL the target is missing relative to the baseline",
    )
    mode.add_argument(
        "--apply",
        metavar="DDL.sql",
        help=f"execute a --diff DDL file. Only ever against {ALLOWED_WRITE_DB_NAME}.",
    )

    parser.add_argument("--server", default=None, help=f"default: $SLP_DB_SERVER or {DEFAULT_SERVER}")
    parser.add_argument("--database", default=None, help="default: $SLP_DB_NAME (required)")
    parser.add_argument(
        "--driver",
        default=os.environ.get("SLP_ODBC_DRIVER", DEFAULT_ODBC_DRIVER),
        help=f"default: $SLP_ODBC_DRIVER or {DEFAULT_ODBC_DRIVER}",
    )
    parser.add_argument(
        "--auth",
        choices=("token", "azcli"),
        default=os.environ.get("SLP_DB_AUTH", "token"),
        help="token: az CLI token via SQL_COPT_SS_ACCESS_TOKEN (default). "
        "azcli: Authentication=ActiveDirectoryAzCli",
    )
    parser.add_argument("--out", default=None, help="output file for --compare and --diff")
    parser.add_argument("--dry-run", action="store_true", help="--apply: list the batches, execute nothing")
    parser.add_argument(
        "--skip-stamp",
        action="store_true",
        help="--provision: create the tables but do not run `alembic stamp head`",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.compare and not args.out:
        parser.error("--compare requires --out FILE.json")
    if args.diff and not args.out:
        parser.error("--diff requires --out FILE.sql")

    try:
        if args.provision:
            return mode_provision(args)
        if args.compare:
            return mode_compare(args)
        if args.diff:
            return mode_diff(args)
        if args.apply:
            return mode_apply(args)
    except GuardViolation as exc:
        print(f"GUARD: {exc}", file=sys.stderr)
        return 2
    except CatalogOnlyViolation as exc:
        print(f"CATALOG-ONLY VIOLATION: {exc}", file=sys.stderr)
        return 3
    return parser.error("no mode selected")  # unreachable: the group is required


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
