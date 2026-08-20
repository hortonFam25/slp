from __future__ import annotations

import json
import logging

from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies.auth import AuthContext, ensure_student_access, get_auth_context
from app.db.database import get_db
from app.schemas.ai_chat import (
    AIChatMessageCreate,
    AIChatMessageEditRequest,
    AIChatMessagePairRead,
    AIChatMessageRead,
    AISaveProgressNoteRequest,
    AIUpdateProgressNoteRequest,
    AISavedProgressNoteRead,
    AIChatSessionCreate,
    AIChatSessionRead,
)
from app.services.ai_chat_service import AIChatService


router = APIRouter(prefix="/api/ai-chat", tags=["ai-chat"])
logger = logging.getLogger(__name__)


@router.post("/sessions", response_model=AIChatSessionRead)
def create_chat_session(
    payload: AIChatSessionCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if payload.student_id is not None:
        ensure_student_access(auth, payload.student_id, action="create ai chat session")
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        return service.create_session(student_id=payload.student_id, title=payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[AIChatSessionRead])
def list_chat_sessions(
    student_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if student_id is not None:
        ensure_student_access(auth, student_id, action="list ai chat sessions")
    service = AIChatService(db, user_id=auth.effective_user.id)
    return service.list_sessions(student_id=student_id)


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        service.delete_session(session_id=session_id)
        return {"message": "Chat session deleted successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/messages", response_model=list[AIChatMessageRead])
def list_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        return service.list_messages(chat_session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages", response_model=AIChatMessageRead)
def post_chat_message(
    session_id: int,
    payload: AIChatMessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        return service.send_message(chat_session_id=session_id, content=payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}/messages/{message_id}/edit-and-regenerate", response_model=AIChatMessagePairRead)
def patch_chat_message_edit_and_regenerate(
    session_id: int,
    message_id: int,
    payload: AIChatMessageEditRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        user_message, assistant_message = service.edit_last_user_message(
            chat_session_id=session_id,
            message_id=message_id,
            content=payload.content,
        )
        return AIChatMessagePairRead(user_message=user_message, assistant_message=assistant_message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/messages/stream")
async def post_chat_message_stream(
    session_id: int,
    payload: AIChatMessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    db.close()

    async def event_generator():
        try:
            async for event in service.stream_message(chat_session_id=session_id, content=payload.content):
                yield f"data: {json.dumps(jsonable_encoder(event))}\n\n"
        except ValueError as exc:
            logger.warning("AI chat streaming validation error: %s", exc)
            error_event = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(jsonable_encoder(error_event))}\n\n"
        except Exception as exc:
            logger.exception("AI chat streaming failed")
            error_event = {"type": "error", "message": f"Unexpected streaming error: {exc}"}
            yield f"data: {json.dumps(jsonable_encoder(error_event))}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/sessions/{session_id}/messages/{message_id}")
def delete_chat_message(
    session_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        service.delete_message(chat_session_id=session_id, message_id=message_id)
        return {"message": "Chat message deleted successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/save-progress-note", response_model=AISavedProgressNoteRead)
def save_progress_note(
    session_id: int,
    payload: AISaveProgressNoteRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        return service.save_progress_note(
            chat_session_id=session_id,
            title=payload.title,
            note_content=payload.note_content,
            template_version=payload.template_version,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/saved-progress-notes", response_model=list[AISavedProgressNoteRead])
def list_saved_progress_notes(
    student_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if student_id is not None:
        ensure_student_access(auth, student_id, action="list saved progress notes")
    service = AIChatService(db, user_id=auth.effective_user.id)
    return service.list_saved_progress_notes(student_id=student_id)


@router.patch("/saved-progress-notes/{note_id}", response_model=AISavedProgressNoteRead)
def update_saved_progress_note(
    note_id: int,
    payload: AIUpdateProgressNoteRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        return service.update_saved_progress_note(
            note_id=note_id,
            title=payload.title,
            note_content=payload.note_content,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/saved-progress-notes/{note_id}")
def delete_saved_progress_note(
    note_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    service = AIChatService(db, user_id=auth.effective_user.id)
    try:
        service.delete_saved_progress_note(note_id=note_id)
        return {"message": "Saved progress note deleted successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

