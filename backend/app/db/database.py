from __future__ import annotations

import time
import logging
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, exc
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from app.settings import settings
from app.db.pause_signatures import is_serverless_pause_error

logger = logging.getLogger(__name__)


# Ensure SQLite has FK constraints when used locally; safe no-op for MSSQL
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-redef]
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


# The pause signatures used to live here as a private copy. They now live in
# app.db.pause_signatures so the request-level 503 handler and the readiness
# probe classify a failure exactly the way these retry loops do. The alias keeps
# the old private name working for anything that still reaches for it.
_is_serverless_pause_error = is_serverless_pause_error


def _create_engine_with_retry(max_retry_duration: int = 300, initial_delay: float = 1.0):
    """
    Create SQLAlchemy engine with robust retry logic for Azure SQL serverless.
    
    Args:
        max_retry_duration: Maximum time to retry in seconds (default: 5 minutes)
        initial_delay: Initial delay between retries in seconds
    """
    start_time = time.time()
    attempt = 1
    last_exc: Exception | None = None
    
    # Enhanced connection args for Azure SQL serverless
    connection_string = settings.sql_server_connection_string or "sqlite:///./local.db"
    is_azure_sql = "database.windows.net" in connection_string
    
    connect_args = {}
    if "sqlite" in connection_string:
        connect_args = {"timeout": 30}
    elif is_azure_sql:
        connect_args = {
            "timeout": 60,  # Increased timeout for serverless resume
            "command_timeout": 60,
        }
    
    while time.time() - start_time < max_retry_duration:
        try:
            logger.info(f"Creating database engine (attempt {attempt})")
            
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                pool_size=3,  # Smaller pool for serverless
                max_overflow=5,
                pool_recycle=3600,  # Recycle connections more frequently
                pool_timeout=60,
                connect_args=connect_args,
                echo=False,  # Set to True for debugging
                implicit_returning=False,  # Fix for SQL Server trigger compatibility
            )
            
            # Test connection with retry logic
            logger.info("Testing database connection...")
            with engine.connect() as conn:
                # Simple query to verify connection
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
                    
            logger.info("Database connection successful!")
            return engine
            
        except Exception as exc:
            last_exc = exc
            elapsed = time.time() - start_time
            
            if _is_serverless_pause_error(exc):
                logger.warning(
                    f"Azure SQL serverless appears to be paused/starting (attempt {attempt}, "
                    f"elapsed: {elapsed:.1f}s): {exc}"
                )
            else:
                logger.error(
                    f"Database connection failed (attempt {attempt}, "
                    f"elapsed: {elapsed:.1f}s): {exc}"
                )
            
            # Stop retrying if we've exceeded max duration
            if elapsed >= max_retry_duration:
                logger.error(f"Giving up after {elapsed:.1f} seconds")
                break
                
            # Calculate exponential backoff delay (cap at 30 seconds)
            delay = min(initial_delay * (2 ** (attempt - 1)), 30.0)
            
            # If it looks like serverless pause, use longer delays
            if _is_serverless_pause_error(exc):
                delay = max(delay, 10.0)  # Minimum 10 second delay for serverless
                
            remaining_time = max_retry_duration - elapsed
            if remaining_time > delay:
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                attempt += 1
            else:
                logger.error(f"Not enough time remaining for retry ({remaining_time:.1f}s < {delay:.1f}s)")
                break
    
    raise last_exc or RuntimeError(
        f"Failed to initialize database engine after {max_retry_duration} seconds"
    )


engine = _create_engine_with_retry()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# The readiness probe's own engine.
# ---------------------------------------------------------------------------
# `engine` above is tuned to *survive* a pause: a 60-second login timeout, a
# connection pool, pool_pre_ping. That is right for real work and exactly wrong
# for /api/health/ready, which the browser polls every 5 seconds and which has
# to answer "still asleep" in a couple of seconds rather than block for a minute
# holding a worker.
#
# So the probe gets its own engine: same URL, NullPool (never hand a probe
# connection to anyone else, never keep one), and a short login timeout so a
# paused database comes back as an error we can classify instead of a hang.
# Built lazily and cached — create_engine() does not connect, but there is no
# reason to build it in a process that never probes.
PROBE_CONNECT_TIMEOUT_SECONDS = 3
PROBE_STATEMENT_TIMEOUT_SECONDS = 3

_probe_engine: Engine | None = None


def get_probe_engine() -> Engine:
    """A short-timeout, unpooled engine for liveness/readiness probing only."""
    global _probe_engine
    if _probe_engine is not None:
        return _probe_engine

    from sqlalchemy.pool import NullPool

    connection_string = settings.sql_server_connection_string or "sqlite:///./local.db"
    connect_args: dict = {}
    if "sqlite" in connection_string:
        connect_args = {"timeout": PROBE_CONNECT_TIMEOUT_SECONDS}
    elif "database.windows.net" in connection_string:
        connect_args = {
            "timeout": PROBE_CONNECT_TIMEOUT_SECONDS,
            "command_timeout": PROBE_CONNECT_TIMEOUT_SECONDS,
        }

    # No implicit_returning=False here, unlike the main engine: that flag exists
    # to keep INSERT..OUTPUT away from trigger-bearing tables, and this engine
    # only ever runs SELECT 1.
    _probe_engine = create_engine(
        connection_string,
        poolclass=NullPool,
        connect_args=connect_args,
        echo=False,
    )
    return _probe_engine


def probe_database() -> None:
    """Run the cheapest possible query, fast. Raises on any failure.

    The caller classifies the exception with
    ``app.db.pause_signatures.is_serverless_pause_error``; this function's only
    job is to fail *quickly* rather than to fail informatively.
    """
    from sqlalchemy import text

    with get_probe_engine().connect() as conn:
        # pyodbc puts the statement timeout on the connection object, and there
        # is no dialect-neutral way to ask for one. Best effort: every driver
        # that does not support it simply does not get one, and the short login
        # timeout still bounds the common case (a paused DB fails at connect).
        raw = getattr(conn.connection, "dbapi_connection", conn.connection)
        try:
            raw.timeout = PROBE_STATEMENT_TIMEOUT_SECONDS
        except Exception:
            pass
        conn.execute(text("SELECT 1"))


@contextmanager
def get_db_with_retry(max_retry_duration: int = 180):
    """
    Get database session with retry logic for serverless resume.
    
    Args:
        max_retry_duration: Maximum time to retry in seconds (default: 3 minutes)
    """
    start_time = time.time()
    attempt = 1
    last_exc: Exception | None = None
    
    while time.time() - start_time < max_retry_duration:
        db = None
        try:
            db = SessionLocal()
            # Test the connection with a simple query
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            yield db
            return  # Success, exit the retry loop
            
        except Exception as exc:
            last_exc = exc
            elapsed = time.time() - start_time
            
            if db:
                db.close()
                
            if _is_serverless_pause_error(exc):
                logger.warning(
                    f"Database session failed due to serverless pause (attempt {attempt}, "
                    f"elapsed: {elapsed:.1f}s): {exc}"
                )
                
                # Calculate delay for serverless resume
                delay = min(10.0 * attempt, 30.0)  # 10s, 20s, 30s, 30s...
                remaining_time = max_retry_duration - elapsed
                
                if remaining_time > delay:
                    logger.info(f"Retrying database session in {delay:.1f} seconds...")
                    time.sleep(delay)
                    attempt += 1
                    continue
                else:
                    logger.error(f"Not enough time remaining for retry ({remaining_time:.1f}s < {delay:.1f}s)")
                    break
            else:
                # Non-serverless error, don't retry
                logger.error(f"Database session failed with non-retryable error: {exc}")
                break
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
    
    # If we get here, all retries failed
    raise last_exc or RuntimeError(
        f"Failed to establish database session after {max_retry_duration} seconds"
    )


def get_db() -> Generator:
    """Standard database session generator (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


