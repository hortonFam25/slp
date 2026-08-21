"""Application-wide exception handlers."""

from app.errors.db_waking import (
    db_waking_json_response,
    register_db_waking_handler,
    sqlalchemy_error_handler,
)

__all__ = [
    "db_waking_json_response",
    "register_db_waking_handler",
    "sqlalchemy_error_handler",
]
