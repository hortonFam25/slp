from __future__ import annotations

from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.ai_chat_message import AIChatMessage
from app.models.ai_chat_session import AIChatSession
from app.models.ai_saved_progress_note import AISavedProgressNote


class AIChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        *,
        user_id: int,
        student_id: int | None,
        student_alias: str | None,
        title: str | None = None,
    ) -> AIChatSession:
        session = AIChatSession(
            user_id=user_id,
            student_id=student_id,
            student_alias=student_alias,
            title=title,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self, *, user_id: int, student_id: int | None = None) -> List[AIChatSession]:
        query = self.db.query(AIChatSession).filter(AIChatSession.user_id == user_id)
        if student_id is not None:
            query = query.filter(AIChatSession.student_id == student_id)
        return query.order_by(AIChatSession.created_date.desc()).all()

    def get_session(self, *, session_id: int, user_id: int) -> AIChatSession | None:
        return (
            self.db.query(AIChatSession)
            .filter(AIChatSession.id == session_id, AIChatSession.user_id == user_id)
            .first()
        )

    def delete_session(self, *, session: AIChatSession) -> None:
        # Keep saved notes but detach them from the deleted chat session.
        for note in session.saved_progress_notes:
            note.chat_session_id = None
            self.db.add(note)
        self.db.delete(session)
        self.db.commit()

    def create_message(
        self,
        *,
        chat_session_id: int,
        role: str,
        model_content: str,
        ui_content: str,
        parent_user_message_id: int | None = None,
    ) -> AIChatMessage:
        message = AIChatMessage(
            chat_session_id=chat_session_id,
            parent_user_message_id=parent_user_message_id,
            role=role,
            model_content=model_content,
            ui_content=ui_content,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, *, chat_session_id: int) -> List[AIChatMessage]:
        return (
            self.db.query(AIChatMessage)
            .filter(AIChatMessage.chat_session_id == chat_session_id)
            .order_by(AIChatMessage.created_date.asc())
            .all()
        )

    def get_message(self, *, message_id: int, chat_session_id: int) -> AIChatMessage | None:
        return (
            self.db.query(AIChatMessage)
            .filter(
                AIChatMessage.id == message_id,
                AIChatMessage.chat_session_id == chat_session_id,
            )
            .first()
        )

    def delete_message(self, *, message: AIChatMessage) -> None:
        self.db.delete(message)
        self.db.commit()

    def update_message_content(
        self,
        *,
        message: AIChatMessage,
        model_content: str,
        ui_content: str,
    ) -> AIChatMessage:
        message.model_content = model_content
        message.ui_content = ui_content
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def create_saved_progress_note(
        self,
        *,
        user_id: int,
        student_id: int,
        student_alias: str,
        title: str,
        note_content: str,
        template_version: str = "v1",
        status: str = "draft",
        chat_session_id: int | None = None,
    ) -> AISavedProgressNote:
        note = AISavedProgressNote(
            chat_session_id=chat_session_id,
            user_id=user_id,
            student_id=student_id,
            student_alias=student_alias,
            title=title,
            note_content=note_content,
            template_version=template_version,
            status=status,
            created_by=user_id,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_saved_progress_notes(
        self,
        *,
        user_id: int,
        student_id: int | None = None,
    ) -> List[AISavedProgressNote]:
        query = self.db.query(AISavedProgressNote).filter(AISavedProgressNote.user_id == user_id)
        if student_id is not None:
            query = query.filter(AISavedProgressNote.student_id == student_id)
        return query.order_by(AISavedProgressNote.created_date.desc()).all()

    def get_saved_progress_note(self, *, note_id: int, user_id: int) -> AISavedProgressNote | None:
        return (
            self.db.query(AISavedProgressNote)
            .filter(AISavedProgressNote.id == note_id, AISavedProgressNote.user_id == user_id)
            .first()
        )

    def update_saved_progress_note(
        self,
        *,
        note: AISavedProgressNote,
        title: str | None = None,
        note_content: str | None = None,
        status: str | None = None,
    ) -> AISavedProgressNote:
        if title is not None:
            note.title = title
        if note_content is not None:
            note.note_content = note_content
        if status is not None:
            note.status = status

        note.modified_date = datetime.utcnow()
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_saved_progress_note(self, *, note: AISavedProgressNote) -> None:
        self.db.delete(note)
        self.db.commit()

