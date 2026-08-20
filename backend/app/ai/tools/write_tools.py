from __future__ import annotations

from typing import Any

from agents import function_tool
from sqlalchemy.orm import Session

from app.ai.privacy import StudentAliasContext, redact_student_name_from_value
from app.db.database import SessionLocal
from app.models.ai_chat_message import AIChatMessage
from app.models.ai_saved_progress_note import AISavedProgressNote


def build_write_tools(
    *,
    db: Session,
    alias_ctx: StudentAliasContext,
    user_id: int,
    chat_session_id: int | None = None,
) -> list[Any]:
    @function_tool
    def save_progress_note_draft(
        note_content: str,
        title: str = "AI Progress Note Draft",
        template_version: str = "v1",
        status: str = "draft",
    ) -> dict[str, Any]:
        """
        Save a generated progress-note draft to AI-specific storage.
        """
        local_db = SessionLocal()
        try:
            sanitized_content = redact_student_name_from_value(note_content, alias_ctx)
            saved = AISavedProgressNote(
                chat_session_id=chat_session_id,
                user_id=user_id,
                student_id=alias_ctx.student_id,
                student_alias=alias_ctx.alias,
                title=title,
                note_content=sanitized_content,
                template_version=template_version,
                status=status,
                created_by=user_id,
            )
            local_db.add(saved)
            local_db.commit()
            local_db.refresh(saved)
            return {
                "saved_progress_note_id": saved.id,
                "student_alias": alias_ctx.alias,
                "status": saved.status,
                "template_version": saved.template_version,
            }
        finally:
            local_db.close()

    @function_tool
    def save_internal_agent_message(role: str, content: str) -> dict[str, Any]:
        """
        Save model-facing chat text to AI chat history.
        """
        if chat_session_id is None:
            return {
                "error": "chat_session_id is required for message persistence",
                "student_alias": alias_ctx.alias,
            }

        local_db = SessionLocal()
        try:
            sanitized_content = redact_student_name_from_value(content, alias_ctx)
            message = AIChatMessage(
                chat_session_id=chat_session_id,
                role=role,
                model_content=sanitized_content,
                ui_content=sanitized_content,
            )
            local_db.add(message)
            local_db.commit()
            local_db.refresh(message)
            return {"saved_message_id": message.id, "student_alias": alias_ctx.alias}
        finally:
            local_db.close()

    return [save_progress_note_draft, save_internal_agent_message]

