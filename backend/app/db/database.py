from __future__ import annotations

import time
import logging
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, exc
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from app.settings import settings

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


def _is_serverless_pause_error(error: Exception) -> bool:
    """Check if the error is related to Azure SQL serverless being paused."""
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in [
        "database is currently unavailable",
        "database is being started", 
        "database is paused",
        "cannot connect to database", 
        "timeout expired",
        "database startup is in progress",
        "40613",  # Azure SQL error code for paused database
        "40501",  # Azure SQL error code for service busy
    ])


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


