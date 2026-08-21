"""The one place that decides "this failure is Azure SQL waking up".

Production runs on Azure SQL Serverless, which auto-pauses after 60 idle
minutes. The first connection after a pause does not fail *fast* and it does not
fail *cleanly* — it fails with one of a handful of driver-level messages while
the compute tier spins back up, which takes roughly 30-60 seconds. Everything
that wants to tell "the database is asleep" apart from "the database is broken"
asks this module, so the answer cannot drift between layers:

* ``app.db.database``          — engine creation / session retry loops
* ``app.db.retry_decorator``   — the ``@db_retry`` wrapper
* ``app.errors.db_waking``     — the request-level 503 handler
* ``app.routers.health``       — the ``/api/health/ready`` probe the UI polls

Both of the retry modules grew their own copy of this list; the two copies had
already diverged (``retry_decorator`` knew about "connection is not available",
``database`` did not). The list below is the union, and both now import it.

A note on ``timeout expired``: it is deliberately kept, because a pyodbc login
timeout against a paused database is exactly how the pause presents itself when
the driver gives up before Azure answers 40613. The cost is that a genuinely
slow query which exhausts its own timeout is also reported as DB_WAKING. That is
the trade the retry loops already made; the request-level handler inherits it,
and the client-side retry budget is bounded (~120s) so a mislabelled slow query
degrades to "retried a few times", not to an infinite loop.
"""

from __future__ import annotations

# The wire contract, shared with the frontend. Documented in docs/DATABASE.md.
DB_WAKING_CODE = "DB_WAKING"
DB_WAKING_DETAIL = "Database is waking up"
DB_WAKING_RETRY_AFTER_SECONDS = 5

# Lowercase substrings. Matched against ``str(exception)``, which for a
# SQLAlchemy DBAPIError includes the driver's own message and SQLSTATE.
PAUSE_SIGNATURES: tuple[str, ...] = (
    "database is currently unavailable",
    "the database is currently unavailable",
    "database is being started",
    "database is paused",
    "cannot connect to database",
    "timeout expired",
    "database startup is in progress",
    "connection is not available",
    "40613",  # Azure SQL: "Database ... is not currently available"
    "40501",  # Azure SQL: service is busy (throttling during resume)
)


def matched_pause_signature(error: BaseException) -> str | None:
    """The signature that classified ``error``, or None.

    Returned so that logs can say *why* a request was called a pause without
    echoing the driver's message, which carries the SQL text and its bound
    parameters — i.e. patient data. The signatures themselves are constants from
    the tuple above and are safe to log.
    """
    error_str = str(error).lower()
    for signature in PAUSE_SIGNATURES:
        if signature in error_str:
            return signature
    return None


def is_serverless_pause_error(error: BaseException) -> bool:
    """True when ``error`` looks like Azure SQL Serverless resuming from pause."""
    return matched_pause_signature(error) is not None
