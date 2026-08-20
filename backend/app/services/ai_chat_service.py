from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents import Runner
from sqlalchemy.orm import Session

from app.ai.privacy import (
    build_alias_context,
    hydrate_aliases_for_ui,
    redact_student_name_from_value,
)
from app.ai.orchestrator import build_supervisor_agent
from app.ai.tools.agent_tools import build_general_specialist_tools, build_specialist_tools
from app.models.ai_chat_message import AIChatMessage
from app.models.student import Student
from app.repositories.ai_chat_repository import AIChatRepository
from app.schemas.ai_chat import (
    AIChatMessageRead,
    AISavedProgressNoteRead,
    AIChatSessionRead,
)
from app.settings import settings


class AIChatService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repo = AIChatRepository(db)

    def _release_db_connection(self) -> None:
        self.db.close()

    def _get_student_or_raise(self, student_id: int) -> Student:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise ValueError("Student not found")
        return student

    def _build_alias_context(self, student_id: int):
        student = self._get_student_or_raise(student_id)
        return build_alias_context(
            student_id=student.id,
            first_name=student.first,
            last_name=student.last,
        )

    def _list_completed_turn_messages(self, *, chat_session_id: int) -> list[AIChatMessage]:
        """
        Return only messages that belong to completed user->assistant turns.

        Primary strategy uses explicit linkage (assistant.parent_user_message_id).
        A legacy fallback is kept for sessions that predate linkage backfill.
        """
        ordered_messages = self.repo.list_messages(chat_session_id=chat_session_id)
        if not ordered_messages:
            return []

        users_by_id = {
            message.id: message for message in ordered_messages if (message.role or "").lower() == "user"
        }
        linked_assistants = [
            message
            for message in ordered_messages
            if (message.role or "").lower() == "assistant" and message.parent_user_message_id is not None
        ]
        if linked_assistants:
            completed: list[AIChatMessage] = []
            for assistant in linked_assistants:
                user = users_by_id.get(assistant.parent_user_message_id)
                if not user:
                    continue
                completed.extend([user, assistant])
            return completed

        # Legacy fallback for old rows without explicit linkage.
        completed = []
        pending_user: AIChatMessage | None = None
        for message in ordered_messages:
            role = (message.role or "").lower()
            if role == "user":
                pending_user = message
            elif role == "assistant" and pending_user is not None:
                completed.extend([pending_user, message])
                pending_user = None
        return completed

    def _to_message_read(self, message: AIChatMessage) -> AIChatMessageRead:
        return AIChatMessageRead(
            id=message.id,
            chat_session_id=message.chat_session_id,
            role=message.role,
            content=message.ui_content,
            created_date=message.created_date,
        )

    def _find_paired_message(
        self,
        *,
        chat_session_id: int,
        message: AIChatMessage,
    ) -> AIChatMessage | None:
        role = (message.role or "").lower()

        # Explicit linkage path.
        if role == "assistant" and message.parent_user_message_id is not None:
            return self.repo.get_message(
                message_id=message.parent_user_message_id,
                chat_session_id=chat_session_id,
            )
        if role == "user":
            linked_assistant = (
                self.db.query(AIChatMessage)
                .filter(
                    AIChatMessage.chat_session_id == chat_session_id,
                    AIChatMessage.role == "assistant",
                    AIChatMessage.parent_user_message_id == message.id,
                )
                .first()
            )
            if linked_assistant:
                return linked_assistant

        # Legacy fallback for old, unlinked rows: derive pair from completed ordering.
        completed = self._list_completed_turn_messages(chat_session_id=chat_session_id)
        for idx, item in enumerate(completed):
            if item.id != message.id:
                continue
            if idx % 2 == 0 and idx + 1 < len(completed):
                return completed[idx + 1]
            if idx % 2 == 1 and idx - 1 >= 0:
                return completed[idx - 1]
        return None

    def _extract_tool_name(self, item: Any) -> str:
        for attr in ("tool_name", "name"):
            value = getattr(item, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raw_item = getattr(item, "raw_item", None)
        if raw_item is not None:
            for attr in ("name", "tool_name"):
                value = getattr(raw_item, attr, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return "tool"

    def _extract_tool_call_id(self, item: Any) -> str | None:
        for attr in ("call_id", "tool_call_id", "id"):
            value = getattr(item, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raw_item = getattr(item, "raw_item", None)
        if raw_item is not None:
            for attr in ("call_id", "id"):
                value = getattr(raw_item, attr, None)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def build_orchestrator(
        self,
        *,
        student_id: int | None,
        chat_session_id: int,
        progress_callback: Any | None = None,
    ) -> Any:
        if student_id is None:
            # General chat mode uses only non-student-specific web research.
            return build_supervisor_agent(
                tools=build_general_specialist_tools(progress_callback=progress_callback)
            )
        specialist_tools = build_specialist_tools(
            db=self.db,
            user_id=self.user_id,
            student_id=student_id,
            chat_session_id=chat_session_id,
            progress_callback=progress_callback,
        )
        return build_supervisor_agent(tools=specialist_tools)

    def _estimate_token_count(self, text: str) -> int:
        # Lightweight estimate commonly used for rough budgeting.
        return max(1, len(text) // 4)

    def _build_history_window_from_messages(
        self,
        *,
        messages: list[AIChatMessage],
        latest_user_content: str | None = None,
    ) -> list[dict[str, str]]:
        max_messages = max(1, settings.ai_chat_history_max_messages)
        max_tokens = max(256, settings.ai_chat_history_max_input_tokens)

        selected: list[dict[str, str]] = []
        used_tokens = 0

        # Walk backwards to prefer the most recent conversational context.
        for message in reversed(messages):
            content = (message.model_content or "").strip()
            if not content:
                continue

            role = "assistant" if message.role == "assistant" else "user"
            estimated_tokens = self._estimate_token_count(content) + 4

            if not selected and estimated_tokens > max_tokens:
                # Keep the latest message even if large by trimming to budget.
                max_chars = max(256, max_tokens * 4)
                content = content[-max_chars:]
                estimated_tokens = self._estimate_token_count(content) + 4

            if selected and (used_tokens + estimated_tokens > max_tokens):
                break

            selected.append({"role": role, "content": content})
            used_tokens += estimated_tokens

            if len(selected) >= max_messages:
                break

        selected.reverse()

        if latest_user_content:
            content = latest_user_content.strip()
            if content:
                selected.append({"role": "user", "content": content})
        return selected

    def _build_history_window_input(
        self,
        *,
        chat_session_id: int,
        latest_user_content: str | None = None,
    ) -> list[dict[str, str]]:
        messages = self._list_completed_turn_messages(chat_session_id=chat_session_id)
        return self._build_history_window_from_messages(
            messages=messages,
            latest_user_content=latest_user_content,
        )

    def create_session(self, *, student_id: int | None, title: str | None = None) -> AIChatSessionRead:
        alias_ctx = self._build_alias_context(student_id) if student_id is not None else None
        session = self.repo.create_session(
            user_id=self.user_id,
            student_id=student_id,
            student_alias=alias_ctx.alias if alias_ctx else None,
            title=title,
        )
        return AIChatSessionRead.model_validate(session)

    def list_sessions(self, *, student_id: int | None = None) -> list[AIChatSessionRead]:
        sessions = self.repo.list_sessions(user_id=self.user_id, student_id=student_id)
        return [AIChatSessionRead.model_validate(item) for item in sessions]

    def delete_session(self, *, session_id: int) -> None:
        session = self.repo.get_session(session_id=session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")
        self.repo.delete_session(session=session)

    def list_messages(self, *, chat_session_id: int) -> list[AIChatMessageRead]:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")

        messages = self._list_completed_turn_messages(chat_session_id=chat_session_id)
        return [self._to_message_read(item) for item in messages]

    def send_message(self, *, chat_session_id: int, content: str) -> AIChatMessageRead:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")

        student_id = session.student_id
        alias_ctx = self._build_alias_context(student_id) if student_id is not None else None
        sanitized_user_content = (
            redact_student_name_from_value(content, alias_ctx) if alias_ctx else content
        )

        user_message = self.repo.create_message(
            chat_session_id=chat_session_id,
            role="user",
            model_content=sanitized_user_content,
            ui_content=content,
        )

        history_window_input = self._build_history_window_input(
            chat_session_id=chat_session_id,
            latest_user_content=sanitized_user_content,
        )

        orchestrator = self.build_orchestrator(
            student_id=student_id,
            chat_session_id=chat_session_id,
        )
        user_message_id = user_message.id
        self._release_db_connection()

        try:
            result = Runner.run_sync(orchestrator, input=history_window_input)
            assistant_model_content = str(getattr(result, "final_output", "") or "").strip()
            if not assistant_model_content:
                assistant_model_content = (
                    "I could not generate a response from the current context. "
                    "Please try rephrasing your request."
                )
        except Exception:
            assistant_model_content = (
                "I ran into a temporary issue while processing that request. "
                "Please try again."
            )

        if alias_ctx:
            assistant_model_content = redact_student_name_from_value(assistant_model_content, alias_ctx)
            assistant_ui_content = hydrate_aliases_for_ui(assistant_model_content, alias_ctx)
        else:
            assistant_ui_content = assistant_model_content

        saved = self.repo.create_message(
            chat_session_id=chat_session_id,
            role="assistant",
            model_content=assistant_model_content,
            ui_content=assistant_ui_content,
            parent_user_message_id=user_message_id,
        )

        return self._to_message_read(saved)

    def edit_last_user_message(
        self,
        *,
        chat_session_id: int,
        message_id: int,
        content: str,
    ) -> tuple[AIChatMessageRead, AIChatMessageRead]:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")

        message = self.repo.get_message(message_id=message_id, chat_session_id=chat_session_id)
        if not message or (message.role or "").lower() != "user":
            raise ValueError("Editable user message not found")

        completed = self._list_completed_turn_messages(chat_session_id=chat_session_id)
        last_user = next((item for item in reversed(completed) if (item.role or "").lower() == "user"), None)
        if not last_user or last_user.id != message.id:
            raise ValueError("Only the last user message can be edited")

        paired_assistant = self._find_paired_message(chat_session_id=chat_session_id, message=message)
        if not paired_assistant or (paired_assistant.role or "").lower() != "assistant":
            raise ValueError("Paired assistant message not found")

        student_id = session.student_id
        alias_ctx = self._build_alias_context(student_id) if student_id is not None else None
        sanitized_user_content = (
            redact_student_name_from_value(content, alias_ctx) if alias_ctx else content
        )

        history_without_current_pair = [
            item for item in completed if item.id not in {message.id, paired_assistant.id}
        ]
        history_window_input = self._build_history_window_from_messages(
            messages=history_without_current_pair,
            latest_user_content=sanitized_user_content,
        )

        orchestrator = self.build_orchestrator(
            student_id=student_id,
            chat_session_id=chat_session_id,
        )
        self._release_db_connection()

        try:
            result = Runner.run_sync(orchestrator, input=history_window_input)
            assistant_model_content = str(getattr(result, "final_output", "") or "").strip()
            if not assistant_model_content:
                assistant_model_content = (
                    "I could not generate a response from the current context. "
                    "Please try rephrasing your request."
                )
        except Exception:
            assistant_model_content = (
                "I ran into a temporary issue while processing that request. "
                "Please try again."
            )

        if alias_ctx:
            assistant_model_content = redact_student_name_from_value(assistant_model_content, alias_ctx)
            assistant_ui_content = hydrate_aliases_for_ui(assistant_model_content, alias_ctx)
        else:
            assistant_ui_content = assistant_model_content

        updated_user = self.repo.update_message_content(
            message=message,
            model_content=sanitized_user_content,
            ui_content=content,
        )
        updated_assistant = self.repo.update_message_content(
            message=paired_assistant,
            model_content=assistant_model_content,
            ui_content=assistant_ui_content,
        )
        return (self._to_message_read(updated_user), self._to_message_read(updated_assistant))

    async def stream_message(
        self,
        *,
        chat_session_id: int,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")

        student_id = session.student_id
        alias_ctx = self._build_alias_context(student_id) if student_id is not None else None
        sanitized_user_content = (
            redact_student_name_from_value(content, alias_ctx) if alias_ctx else content
        )

        user_message = self.repo.create_message(
            chat_session_id=chat_session_id,
            role="user",
            model_content=sanitized_user_content,
            ui_content=content,
        )

        history_window_input = self._build_history_window_input(
            chat_session_id=chat_session_id,
            latest_user_content=sanitized_user_content,
        )

        collected_chunks: list[str] = []
        fallback_used = False
        stream_id = str(uuid4())
        event_sequence = 0
        output_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        producer_done = asyncio.Event()

        def make_event(event: dict[str, Any]) -> dict[str, Any]:
            nonlocal event_sequence
            event_sequence += 1
            payload = dict(event)
            payload["request_id"] = stream_id
            payload["sequence"] = event_sequence
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            return payload

        def emit_progress(event: dict[str, Any]) -> None:
            output_queue.put_nowait(make_event(event))

        orchestrator = self.build_orchestrator(
            student_id=student_id,
            chat_session_id=chat_session_id,
            progress_callback=emit_progress,
        )
        user_message_id = user_message.id
        self._release_db_connection()

        yield make_event(
            {
                "type": "status",
                "source": "system",
                "status": "running",
                "label": "Starting agent run",
            }
        )

        async def _produce_stream_events() -> None:
            try:
                stream_result = Runner.run_streamed(orchestrator, input=history_window_input)
                async for event in stream_result.stream_events():
                    if event.type == "agent_updated_stream_event":
                        new_agent = getattr(event, "new_agent", None)
                        agent_name = getattr(new_agent, "name", None)
                        if isinstance(agent_name, str) and agent_name.strip():
                            output_queue.put_nowait(
                                make_event(
                                    {
                                        "type": "agent_update",
                                        "source": "supervisor",
                                        "agent_name": agent_name.strip(),
                                        "label": f"Active agent: {agent_name.strip()}",
                                    }
                                )
                            )
                        continue

                    if event.type == "run_item_stream_event":
                        item = getattr(event, "item", None)
                        item_type = getattr(item, "type", None)
                        if item is None or not isinstance(item_type, str):
                            continue
                        if item_type == "tool_call_item":
                            tool_name = self._extract_tool_name(item)
                            output_queue.put_nowait(
                                make_event(
                                    {
                                        "type": "tool_call_started",
                                        "source": "supervisor",
                                        "agent_name": "SLPProSupervisor",
                                        "tool_name": tool_name,
                                        "tool_call_id": self._extract_tool_call_id(item),
                                        "label": f"Supervisor using {tool_name}",
                                    }
                                )
                            )
                            continue
                        if item_type == "tool_call_output_item":
                            tool_name = self._extract_tool_name(item)
                            output_queue.put_nowait(
                                make_event(
                                    {
                                        "type": "tool_call_finished",
                                        "source": "supervisor",
                                        "agent_name": "SLPProSupervisor",
                                        "tool_name": tool_name,
                                        "tool_call_id": self._extract_tool_call_id(item),
                                        "label": f"Supervisor finished {tool_name}",
                                    }
                                )
                            )
                        continue

                    if event.type != "raw_response_event":
                        continue
                    data = getattr(event, "data", None)
                    if not data or getattr(data, "type", None) != "response.output_text.delta":
                        continue
                    delta = str(getattr(data, "delta", "") or "")
                    if not delta:
                        continue
                    output_queue.put_nowait(make_event({"type": "delta", "delta": delta}))
            finally:
                producer_done.set()

        producer_task = asyncio.create_task(_produce_stream_events())
        producer_error: Exception | None = None
        while not producer_done.is_set() or not output_queue.empty():
            try:
                next_event = await asyncio.wait_for(output_queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            if next_event.get("type") == "delta":
                delta_value = str(next_event.get("delta", "") or "")
                if delta_value:
                    collected_chunks.append(delta_value)
            yield next_event

        try:
            await producer_task
        except Exception as exc:
            producer_error = exc

        if producer_error is not None:
            fallback_used = True
            fallback_message = (
                "I ran into a temporary issue while processing that request. "
                "Please try again."
            )
            if not collected_chunks:
                collected_chunks = [fallback_message]
                yield make_event({"type": "delta", "delta": fallback_message})

        assistant_model_content = "".join(collected_chunks).strip()
        if not assistant_model_content:
            fallback_used = True
            assistant_model_content = (
                "I could not generate a response from the current context. "
                "Please try rephrasing your request."
            )
            yield make_event({"type": "delta", "delta": assistant_model_content})

        if alias_ctx:
            assistant_model_content = redact_student_name_from_value(assistant_model_content, alias_ctx)
            assistant_ui_content = hydrate_aliases_for_ui(assistant_model_content, alias_ctx)
        else:
            assistant_ui_content = assistant_model_content

        saved = self.repo.create_message(
            chat_session_id=chat_session_id,
            role="assistant",
            model_content=assistant_model_content,
            ui_content=assistant_ui_content,
            parent_user_message_id=user_message_id,
        )

        saved_message = AIChatMessageRead(
            id=saved.id,
            chat_session_id=saved.chat_session_id,
            role=saved.role,
            content=saved.ui_content,
            created_date=saved.created_date,
        )
        message_payload = {
            "id": saved_message.id,
            "chat_session_id": saved_message.chat_session_id,
            "role": saved_message.role,
            "content": saved_message.content,
            "created_date": saved_message.created_date.isoformat(),
        }
        yield make_event({"type": "status", "source": "system", "status": "finalizing", "label": "Saving response"})
        yield make_event(
            {
                "type": "done",
                "message": message_payload,
                "fallback_used": fallback_used,
            }
        )

    def delete_message(self, *, chat_session_id: int, message_id: int) -> None:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")

        message = self.repo.get_message(message_id=message_id, chat_session_id=chat_session_id)
        if not message:
            raise ValueError("Chat message not found")
        paired_message = self._find_paired_message(chat_session_id=chat_session_id, message=message)

        # Delete assistant first if present to satisfy FK dependency to user row.
        to_delete: list[AIChatMessage] = []
        for candidate in (message, paired_message):
            if candidate is None:
                continue
            if all(existing.id != candidate.id for existing in to_delete):
                to_delete.append(candidate)
        to_delete.sort(key=lambda item: 0 if (item.role or "").lower() == "assistant" else 1)

        for item in to_delete:
            self.db.delete(item)
        self.db.commit()

    def save_progress_note(
        self,
        *,
        chat_session_id: int,
        title: str,
        note_content: str,
        template_version: str = "v1",
        status: str = "draft",
    ) -> AISavedProgressNoteRead:
        session = self.repo.get_session(session_id=chat_session_id, user_id=self.user_id)
        if not session:
            raise ValueError("Chat session not found")
        if session.student_id is None:
            raise ValueError("Cannot save a progress note for a general chat session")

        alias_ctx = self._build_alias_context(session.student_id)
        sanitized_note_content = redact_student_name_from_value(note_content, alias_ctx)

        saved = self.repo.create_saved_progress_note(
            user_id=self.user_id,
            student_id=session.student_id,
            student_alias=alias_ctx.alias,
            chat_session_id=chat_session_id,
            title=title,
            note_content=sanitized_note_content,
            template_version=template_version,
            status=status,
        )
        return AISavedProgressNoteRead.model_validate(saved)

    def list_saved_progress_notes(self, *, student_id: int | None = None) -> list[AISavedProgressNoteRead]:
        notes = self.repo.list_saved_progress_notes(user_id=self.user_id, student_id=student_id)
        return [AISavedProgressNoteRead.model_validate(item) for item in notes]

    def update_saved_progress_note(
        self,
        *,
        note_id: int,
        title: str | None = None,
        note_content: str | None = None,
        status: str | None = None,
    ) -> AISavedProgressNoteRead:
        note = self.repo.get_saved_progress_note(note_id=note_id, user_id=self.user_id)
        if not note:
            raise ValueError("Saved progress note not found")

        sanitized_note_content = note_content
        if note_content is not None:
            alias_ctx = self._build_alias_context(note.student_id)
            sanitized_note_content = redact_student_name_from_value(note_content, alias_ctx)

        updated = self.repo.update_saved_progress_note(
            note=note,
            title=title,
            note_content=sanitized_note_content,
            status=status,
        )
        return AISavedProgressNoteRead.model_validate(updated)

    def delete_saved_progress_note(self, *, note_id: int) -> None:
        note = self.repo.get_saved_progress_note(note_id=note_id, user_id=self.user_id)
        if not note:
            raise ValueError("Saved progress note not found")
        self.repo.delete_saved_progress_note(note=note)
