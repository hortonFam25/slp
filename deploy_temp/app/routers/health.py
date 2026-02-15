import time
from fastapi import APIRouter, HTTPException
from app.db.database import engine, get_db_with_retry
from app.db.retry_decorator import db_retry

router = APIRouter()


@router.get("/live")
def liveness():
    """Basic liveness check - always returns true if service is running."""
    return {"live": True}


@router.get("/ready")
def readiness():
    """Readiness check - verifies database connectivity without retry."""
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return {"ready": True, "database": "connected"}
    except Exception as e:
        return {"ready": False, "database": "disconnected", "error": str(e)}


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


