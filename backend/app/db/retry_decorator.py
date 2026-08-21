"""
Database retry decorator for Azure SQL serverless operations.
"""
import time
import logging
import functools
from typing import Callable, Any

from app.db.pause_signatures import is_serverless_pause_error

logger = logging.getLogger(__name__)

# This module used to carry its own copy of the pause signatures, and that copy
# had already drifted from the one in app.db.database. Both now read the single
# list in app.db.pause_signatures; the alias keeps this module's private name.
_is_serverless_pause_error = is_serverless_pause_error


def db_retry(
    max_retry_duration: int = 180,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0
):
    """
    Decorator to add retry logic to database operations for Azure SQL serverless.
    
    Args:
        max_retry_duration: Maximum time to retry in seconds (default: 3 minutes)
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_multiplier: Multiplier for exponential backoff
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            attempt = 1
            last_exc: Exception | None = None
            delay = initial_delay
            
            while time.time() - start_time < max_retry_duration:
                try:
                    return func(*args, **kwargs)
                    
                except Exception as exc:
                    last_exc = exc
                    elapsed = time.time() - start_time
                    
                    if _is_serverless_pause_error(exc):
                        logger.warning(
                            f"Database operation '{func.__name__}' failed due to serverless pause "
                            f"(attempt {attempt}, elapsed: {elapsed:.1f}s): {exc}"
                        )
                        
                        # For serverless pause, use longer minimum delays
                        actual_delay = max(delay, 10.0)
                        remaining_time = max_retry_duration - elapsed
                        
                        if remaining_time > actual_delay:
                            logger.info(f"Retrying '{func.__name__}' in {actual_delay:.1f} seconds...")
                            time.sleep(actual_delay)
                            
                            # Increase delay for next attempt
                            delay = min(delay * backoff_multiplier, max_delay)
                            attempt += 1
                            continue
                        else:
                            logger.error(
                                f"Not enough time remaining for retry of '{func.__name__}' "
                                f"({remaining_time:.1f}s < {actual_delay:.1f}s)"
                            )
                            break
                    else:
                        # Non-serverless error, don't retry
                        logger.error(f"Database operation '{func.__name__}' failed with non-retryable error: {exc}")
                        raise exc
            
            # If we get here, all retries failed
            raise last_exc or RuntimeError(
                f"Database operation '{func.__name__}' failed after {max_retry_duration} seconds"
            )
            
        return wrapper
    return decorator


def db_retry_critical(func: Callable) -> Callable:
    """
    Decorator for critical database operations that need maximum retry duration.
    Uses 5 minute timeout for critical operations.
    """
    return db_retry(max_retry_duration=300)(func)
