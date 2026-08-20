"""Test environment bootstrap.

Everything in here has to happen BEFORE the application is imported, so it runs
at module scope rather than inside a fixture:

* ``backend/`` goes on ``sys.path`` — the app imports itself as ``app.*`` and is
  started as ``main:app``, so ``backend`` is the import root no matter which
  directory pytest was invoked from.
* the settings singleton (``app.settings.settings``) and the SQLAlchemy engine
  (``app.db.database.engine``) are both built at *import* time, so the
  environment they read has to be in place first.

Real environment variables outrank ``backend/.env`` in pydantic-settings, so a
developer's local .env cannot drag these tests onto a real database.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# A throwaway sqlite file in a temp directory. Never the repo's local.db — these
# tests write, and a developer's working database is not ours to touch.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="slppro-tests-"))
_DB_PATH = _TMP_DIR / "test.db"

os.environ["ENVIRONMENT"] = "development"          # enables create_all on startup
os.environ["SQL_SERVER_CONNECTION_STRING"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["AUTH_REQUIRE_BEARER"] = "false"        # anonymous fallback user
os.environ["ACCESS_CONTROL_MODE"] = "monitor"      # observe, do not enforce
os.environ["AUTH_FALLBACK_USER_EXTERNAL_ID"] = "pytest-local-user"
os.environ["AUTH_FALLBACK_USER_EMAIL"] = "pytest@example.invalid"
os.environ["AUTH_FALLBACK_USER_NAME"] = "Pytest Local User"
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
os.environ["PYTHONIOENCODING"] = "utf-8"


# There used to be a `before_cursor_execute` shim here rewriting `GETDATE()` to
# `CURRENT_TIMESTAMP`, because the models hard-coded the SQL-Server-only
# `server_default=text("GETDATE()")` and sqlite's `create_all` died on the first
# CREATE TABLE. The models now use `func.now()`, which each dialect renders for
# itself, so the tests run against unmodified DDL.


@pytest.fixture(scope="session")
def app():
    """The real FastAPI application object, imported the way gunicorn does."""
    from main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    """A TestClient inside the app's lifespan.

    The ``with`` block matters: the ``startup`` handler is what calls
    ``Base.metadata.create_all``, and without it every request would hit an
    empty sqlite file.
    """
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_path() -> Path:
    return _DB_PATH
