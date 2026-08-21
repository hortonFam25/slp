"""Turn "Azure SQL is waking up" into an answer the browser can act on.

Azure SQL Serverless auto-pauses after 60 idle minutes. The first request after
that pause spends 30-60 seconds waiting for compute to resume, and until this
handler existed it ended as an unhandled ``OperationalError`` — a 500 with no
body the client could read, which the browser surfaced to a therapist as a bare
"Network Error" plus an instruction to refresh and hope.

What the handler does instead, for pause failures *only*:

    HTTP 503
    Retry-After: 5
    {"detail": "Database is waking up", "code": "DB_WAKING"}

``code`` is the contract. The frontend keys its retry-and-overlay behaviour off
that string and off nothing else, because the ``detail`` is prose and prose gets
reworded. See docs/DATABASE.md.

Two properties the frontend depends on, and which are worth stating plainly
because a change here silently changes what is safe to retry over there:

1. **A DB_WAKING 503 means the statement never ran.** The failure happens while
   SQLAlchemy is acquiring or checking out a connection, before the transaction
   opens. That is what makes it safe for the client to auto-retry a POST or a
   DELETE that got this response — there is nothing half-written behind it. A
   raw network error carries no such promise, and the frontend does not retry
   writes on one.
2. **Anything that is not a pause is re-raised untouched.** A constraint
   violation, a genuine driver bug, a programming error — all keep whatever
   behaviour they have today (a 500 from Starlette's server-error middleware,
   with the traceback logged). This handler adds a case; it does not become the
   catch-all for database failures.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db.pause_signatures import (
    DB_WAKING_CODE,
    DB_WAKING_DETAIL,
    DB_WAKING_RETRY_AFTER_SECONDS,
    matched_pause_signature,
)

logger = logging.getLogger(__name__)


def db_waking_json_response() -> JSONResponse:
    """The one 503 body. Built here so the probe and the handler cannot drift."""
    return JSONResponse(
        status_code=503,
        content={"detail": DB_WAKING_DETAIL, "code": DB_WAKING_CODE},
        headers={"Retry-After": str(DB_WAKING_RETRY_AFTER_SECONDS)},
    )


def _route_template(request: Request) -> str:
    """``/api/students/{student_id}``, never ``/api/students/4471``.

    The literal path is not safe to log: an id in a URL is a pointer to one
    child. The matched route's template says as much about where the failure
    happened without naming anybody.
    """
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    return template if isinstance(template, str) else "<unmatched>"


async def sqlalchemy_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """503 DB_WAKING for a serverless pause; re-raise everything else."""
    signature = matched_pause_signature(exc)
    if signature is None:
        # Not a pause. Hand it back to Starlette exactly as if we were not
        # registered, so existing behaviour (and existing logging) is unchanged.
        raise exc

    # Warning, not error: this is an expected consequence of the serverless tier
    # and the client is about to retry through it. Nothing here is derived from
    # the exception's message — no SQL text, no bound parameters, no ids.
    logger.warning(
        "Database appears to be resuming from serverless pause "
        "(signature=%r, exception=%s); answering 503 %s for %s %s",
        signature,
        type(exc).__name__,
        DB_WAKING_CODE,
        request.method,
        _route_template(request),
    )
    return db_waking_json_response()


def register_db_waking_handler(app: FastAPI) -> None:
    """Register the handler for every SQLAlchemy failure.

    Registered on ``SQLAlchemyError`` rather than on ``OperationalError``
    specifically: Starlette resolves a handler by walking ``type(exc).__mro__``,
    so the broadest registration catches the pause however the driver chose to
    wrap it (``OperationalError``, ``DBAPIError``, ``InterfaceError``,
    ``DisconnectionError``) without needing a list that has to be kept correct.
    Breadth costs nothing because the handler re-raises anything it does not
    recognise.
    """
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
