"""The archive: what is hidden, who hid it, and how to put it back.

Every DELETE route in this application now archives instead of deleting (same
verbs, same paths, same shapes -- see the routers next to this one). This module
is the other half: the ledger of those archives and the one way to reverse them.

  GET  /api/archive/events                  -- your archive events; all, if admin
  GET  /api/archive/events/{id}             -- one event and what it holds
  POST /api/archive/events/{id}/restore     -- put that event's rows back
  GET  /api/archive/archived/{entity_type}  -- what is currently archived, by type

ACCESS. Archiving and restoring are held to the same check the DELETE they
replaced was: `ensure_student_access` on the student the root entity belongs
to. A time block belongs to a therapist and a school rather than to a child, so
there is no student to check -- which is exactly how the time-block routes have
always worked.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.models.archive_event import ARCHIVABLE_ENTITY_TYPES
from app.services import archive as archive_service

router = APIRouter(prefix="/api/archive", tags=["archive"], dependencies=[Depends(get_auth_context)])


def _scope_ids(auth: AuthContext) -> Optional[list[int]]:
    """The `allowed_student_ids` convention the repositories use."""
    return auth.allowed_student_ids if auth.enforce_access and not auth.is_admin else None


def _require_root_access(db: Session, auth: AuthContext, event, action: str) -> None:
    """The same check the DELETE this event replaced would have made."""
    student_id = archive_service.root_student_id(
        db, event.root_entity_type, event.root_entity_id
    )
    if student_id is not None:
        ensure_student_access(auth, student_id, action=action)


@router.get("/events")
def list_archive_events(
    include_restored: bool = Query(True, description="Include events that have been restored"),
    root_entity_type: Optional[str] = Query(
        None, description="Filter to one root type: student, goal, objective, progress_entry, therapy_session, appointment, time_block"
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Archive events, newest first.

    Scoped to the caller's own events; an admin sees everybody's, which is what
    makes this usable as the audit view it is.
    """
    if root_entity_type is not None and root_entity_type not in ARCHIVABLE_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type '{root_entity_type}'. Expected one of: "
            f"{', '.join(sorted(ARCHIVABLE_ENTITY_TYPES))}.",
        )

    events = archive_service.list_events(
        db,
        user_id=None if auth.is_admin else auth.effective_user.id,
        include_restored=include_restored,
        root_entity_type=root_entity_type,
        limit=limit,
    )
    return [archive_service.event_summary(db, event) for event in events]


@router.get("/events/{event_id}")
def get_archive_event(
    event_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """One archive event, with a count of the rows it still holds."""
    try:
        event = archive_service.get_event(db, event_id)
    except archive_service.EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not auth.is_admin and event.user_id != auth.effective_user.id:
        raise HTTPException(status_code=404, detail="Archive event not found")
    _require_root_access(db, auth, event, action="read archive event")
    return archive_service.event_summary(db, event)


@router.post("/events/{event_id}/restore")
def restore_archive_event(
    event_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Reverse one archive event, and only that event.

    Rows archived under a DIFFERENT event stay archived -- including anything
    that was already archived when this event's cascade ran. Restoring a child
    whose parent is still archived is refused with a 409 naming the parent's
    event, because the alternative is a live row underneath a hidden one.
    """
    try:
        event = archive_service.get_event(db, event_id)
    except archive_service.EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not auth.is_admin and event.user_id != auth.effective_user.id:
        raise HTTPException(status_code=404, detail="Archive event not found")
    _require_root_access(db, auth, event, action="restore archive event")

    try:
        return archive_service.restore(db, user_id=auth.effective_user.id, event_id=event_id)
    except archive_service.AlreadyRestoredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except archive_service.ParentStillArchivedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/archived/{entity_type}")
def list_archived_entities(
    entity_type: str,
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Everything of one type that is currently archived.

    Rows are returned as identity + archive metadata rather than as full
    records: this is the "what is in the archive" screen, and the way to read an
    archived record is to restore it. Student rows are named by ALIAS.
    """
    if entity_type not in ARCHIVABLE_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type '{entity_type}'. Expected one of: "
            f"{', '.join(sorted(ARCHIVABLE_ENTITY_TYPES))}.",
        )

    rows = archive_service.list_archived(
        db,
        entity_type,
        allowed_student_ids=_scope_ids(auth),
        limit=limit,
    )
    return [
        {
            "entityType": entity_type,
            "id": row.id,
            "archivedAt": row.archived_at.isoformat() if row.archived_at else None,
            "archiveEventId": row.archive_event_id,
            "studentAlias": getattr(row, "alias", None) if entity_type == "student" else None,
        }
        for row in rows
    ]
