import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.database import get_db_with_retry, probe_database
from app.db.pause_signatures import (
    DB_WAKING_CODE,
    DB_WAKING_RETRY_AFTER_SECONDS,
    is_serverless_pause_error,
)
from app.db.retry_decorator import db_retry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/live")
def liveness():
    """Basic liveness check - always returns true if service is running.

    Touches nothing. Deliberately: this is what deploy.yml polls to decide the
    zip deploy landed, and what App Service would use to decide whether to
    recycle the worker. A paused database is not a dead process, and wiring a
    query in here would turn every serverless pause into a restart loop.
    """
    return {"live": True}


@router.get("/ready")
def readiness():
    """Is the database reachable *right now*, answered fast either way.

    The browser polls this every 5 seconds while the wake-up overlay is on
    screen, so the contract is about latency as much as truth: it uses the
    short-timeout probe engine (see ``app.db.database.get_probe_engine``) and
    never retries. A paused database comes back in a couple of seconds, not in
    the sixty the main engine would spend being patient.

    Three answers:

    * ``200 {"ready": true,  "database": "connected"}``
    * ``503 {"ready": false, "code": "DB_WAKING", "database": "waking"}``
      plus ``Retry-After: 5`` — Azure SQL Serverless is resuming. Poll again.
    * ``503 {"ready": false, "database": "disconnected"}`` — something else is
      wrong. No ``code``, because the client must not sit in a wake-up loop
      waiting for a misconfigured connection string to fix itself.
    """
    try:
        probe_database()
    except Exception as exc:
        if is_serverless_pause_error(exc):
            logger.warning(
                "Readiness probe: database is resuming from serverless pause (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=503,
                content={"ready": False, "code": DB_WAKING_CODE, "database": "waking"},
                headers={"Retry-After": str(DB_WAKING_RETRY_AFTER_SECONDS)},
            )
        # Not a pause. Still not ready — but say so without the driver's
        # message, which carries connection details and is not the browser's
        # business. The full exception goes to the server log instead.
        logger.exception("Readiness probe failed for a reason that is not a pause")
        return JSONResponse(
            status_code=503,
            content={"ready": False, "database": "disconnected"},
        )
    return {"ready": True, "database": "connected"}


@router.get("/health")
@db_retry(max_retry_duration=60)  # 1 minute retry for health check
def health_check():
    """
    Comprehensive health check with database retry logic.
    This endpoint will retry for up to 1 minute if the database is paused.
    """
    start_time = time.time()
    
    try:
        with get_db_with_retry(max_retry_duration=60) as db:
            # Perform a simple query to verify database connectivity
            from sqlalchemy import text
            result = db.execute(text("SELECT 1 as test_value"))
            test_value = result.fetchone()[0]
            
            connection_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "database": {
                    "connected": True,
                    "test_query_result": test_value,
                    "connection_time_seconds": round(connection_time, 2)
                },
                "timestamp": time.time()
            }
            
    except Exception as e:
        connection_time = time.time() - start_time
        
        return {
            "status": "unhealthy", 
            "database": {
                "connected": False,
                "error": str(e),
                "connection_time_seconds": round(connection_time, 2)
            },
            "timestamp": time.time()
        }


