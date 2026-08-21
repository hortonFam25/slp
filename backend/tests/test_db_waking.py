"""The DB_WAKING contract.

Azure SQL Serverless auto-pauses after 60 idle minutes. These tests pin the two
things the browser is written against, so that neither can be reworded or
"tidied" without a failing test explaining what depends on it:

1. a SQLAlchemy failure whose message carries a pause signature becomes
   ``503 {"detail": ..., "code": "DB_WAKING"}`` with ``Retry-After: 5``;
2. a SQLAlchemy failure that does *not* carry one is untouched — it stays the
   500 it has always been, because the frontend must not sit in a wake-up loop
   waiting for a constraint violation to heal itself.

Everything here runs against sqlite, which never pauses, so the pause is
synthesised: a throwaway route raises a real ``OperationalError`` carrying a
real Azure message. That is exactly the seam the handler classifies on, and it
means the tests do not need a network, a driver, or a paused database.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db.pause_signatures import (
    DB_WAKING_CODE,
    is_serverless_pause_error,
    matched_pause_signature,
)
from app.errors import register_db_waking_handler

# The message Azure SQL actually returns through pyodbc while a serverless
# database is resuming. Kept verbatim, including the 40613, because the
# signature list is matched against driver text and a paraphrase would not
# prove anything.
AZURE_PAUSE_MESSAGE = (
    "('40613', '[40613] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]"
    "Database \\'slppro\\' on server \\'slppro-sql\\' is not currently available. "
    "Please retry the connection later. (40613) (SQLDriverConnect)')"
)


def _pause_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(AZURE_PAUSE_MESSAGE))


def _ordinary_db_error() -> IntegrityError:
    return IntegrityError(
        "INSERT INTO students ...",
        {},
        Exception("UNIQUE constraint failed: students.external_id"),
    )


@pytest.fixture()
def waking_app() -> FastAPI:
    """A minimal app with the handler and two routes that fail on purpose."""
    test_app = FastAPI()
    register_db_waking_handler(test_app)

    @test_app.get("/boom/pause")
    def boom_pause():
        raise _pause_error()

    @test_app.get("/boom/ordinary")
    def boom_ordinary():
        raise _ordinary_db_error()

    @test_app.post("/boom/pause-write")
    def boom_pause_write():
        raise _pause_error()

    @test_app.get("/fine")
    def fine():
        return {"ok": True}

    return test_app


@pytest.fixture()
def waking_client(waking_app: FastAPI) -> TestClient:
    # raise_server_exceptions=False so an unhandled error becomes the 500 a real
    # client would see, rather than being re-raised into the test.
    return TestClient(waking_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# The detector
# ---------------------------------------------------------------------------


def test_azure_pause_message_is_recognised():
    assert is_serverless_pause_error(_pause_error()) is True
    # The signature reported for logging is one of the constants, not a slice
    # of the driver's message — that is what makes it safe to log.
    assert matched_pause_signature(_pause_error()) == "40613"


def test_ordinary_db_error_is_not_a_pause():
    assert is_serverless_pause_error(_ordinary_db_error()) is False
    assert matched_pause_signature(_ordinary_db_error()) is None


def test_detector_is_shared_by_every_layer():
    """One list, four callers. Aliases, not copies — copies had already drifted."""
    from app.db import database, retry_decorator
    from app.db.pause_signatures import is_serverless_pause_error as canonical

    assert database._is_serverless_pause_error is canonical
    assert retry_decorator._is_serverless_pause_error is canonical


# ---------------------------------------------------------------------------
# The handler
# ---------------------------------------------------------------------------


def test_pause_becomes_503_db_waking(waking_client: TestClient):
    response = waking_client.get("/boom/pause")

    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Database is waking up", "code": DB_WAKING_CODE}
    assert response.headers["retry-after"] == "5"


def test_503_body_never_leaks_the_driver_message(waking_client: TestClient):
    """The body is a fixed two-key object. No SQL, no server name, no database name."""
    body = waking_client.get("/boom/pause").text
    assert "40613" not in body
    assert "slppro-sql" not in body
    assert "SELECT 1" not in body


def test_pause_on_a_write_is_also_503_db_waking(waking_client: TestClient):
    """A POST gets the same answer, and that is load-bearing.

    The client auto-retries a *write* on this response, which is only safe
    because a DB_WAKING 503 is raised while acquiring the connection — the
    statement never ran, so there is nothing half-committed behind it.
    """
    response = waking_client.post("/boom/pause-write")

    assert response.status_code == 503, response.text
    assert response.json()["code"] == DB_WAKING_CODE
    assert response.headers["retry-after"] == "5"


def test_ordinary_db_error_still_500s(waking_client: TestClient):
    """Not a pause, not our business. Unchanged behaviour."""
    response = waking_client.get("/boom/ordinary")

    assert response.status_code == 500, response.text
    assert DB_WAKING_CODE not in response.text
    assert "retry-after" not in response.headers


def test_handler_does_not_touch_successful_requests(waking_client: TestClient):
    response = waking_client.get("/fine")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_handler_is_registered_on_the_real_app(app: FastAPI):
    """main.py has to actually call register_db_waking_handler."""
    from sqlalchemy.exc import SQLAlchemyError

    assert SQLAlchemyError in app.exception_handlers


# ---------------------------------------------------------------------------
# The readiness probe
# ---------------------------------------------------------------------------


def test_ready_is_200_when_the_database_answers(client: TestClient):
    """sqlite never pauses, so the happy path is the real one here."""
    response = client.get("/api/health/ready")

    assert response.status_code == 200, response.text
    assert response.json() == {"ready": True, "database": "connected"}


def test_ready_reports_db_waking_while_paused(client: TestClient, monkeypatch):
    from app.routers import health

    def paused_probe() -> None:
        raise _pause_error()

    monkeypatch.setattr(health, "probe_database", paused_probe)
    response = client.get("/api/health/ready")

    assert response.status_code == 503, response.text
    assert response.json() == {
        "ready": False,
        "code": DB_WAKING_CODE,
        "database": "waking",
    }
    assert response.headers["retry-after"] == "5"


def test_ready_is_503_without_a_code_for_other_failures(client: TestClient, monkeypatch):
    """A broken connection string must not park the UI in a wake-up loop."""
    from app.routers import health

    def broken_probe() -> None:
        raise _ordinary_db_error()

    monkeypatch.setattr(health, "probe_database", broken_probe)
    response = client.get("/api/health/ready")

    assert response.status_code == 503, response.text
    body = response.json()
    assert body == {"ready": False, "database": "disconnected"}
    assert "code" not in body
    # And no driver detail on the wire.
    assert "students.external_id" not in response.text


def test_live_stays_database_free(client: TestClient, monkeypatch):
    """The deploy gate polls /live. A paused database must not fail it."""
    from app.routers import health

    def exploding_probe() -> None:  # pragma: no cover - must never be called
        raise AssertionError("/api/health/live touched the database")

    monkeypatch.setattr(health, "probe_database", exploding_probe)
    response = client.get("/api/health/live")

    assert response.status_code == 200, response.text
    assert response.json() == {"live": True}
