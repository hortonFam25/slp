from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

from agents import Runner, function_tool
from sqlalchemy.orm import Session

from app.ai.privacy import StudentAliasContext, build_alias_context, redact_student_name_from_value
from app.ai.specialists.progress_notes_agent import create_progress_notes_agent
from app.ai.specialists.student_read_agent import create_student_read_agent
from app.ai.specialists.web_research_agent import create_web_research_agent
from app.models.student import Student


def _extract_result_text(run_result: Any) -> str:
    final_output = getattr(run_result, "final_output", "")
    return str(final_output) if final_output is not None else ""


def _get_alias_context(db: Session, student_id: int) -> StudentAliasContext:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError("Student not found")
    return build_alias_context(
        student_id=student.id,
        first_name=student.first,
        last_name=student.last,
    )


def _sanitize_for_web_research(text: str, alias_ctx: StudentAliasContext) -> str:
    sanitized = redact_student_name_from_value(text, alias_ctx)
    # Ensure the web specialist never receives student alias identifiers.
    sanitized = re.sub(re.escape(alias_ctx.alias), "a student", sanitized, flags=re.IGNORECASE)
    # Remove generic alias/id forms that may still appear in user prompts.
    sanitized = re.sub(r"\bstudent[_\s-]?\d+\b", "a student", sanitized, flags=re.IGNORECASE)
    return sanitized


def _emit_progress(progress_callback: Callable[[dict[str, Any]], None] | None, event: dict[str, Any]) -> None:
    if not progress_callback:
        return
    progress_callback(event)


def _extract_tool_name(item: Any) -> str:
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


def _extract_tool_call_id(item: Any) -> str | None:
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


async def _run_specialist_with_progress(
    *,
    specialist_name: str,
    specialist_agent: Any,
    input_text: str,
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> str:
    if progress_callback is None:
        result = await Runner.run(specialist_agent, input=input_text)
        result_text = _extract_result_text(result).strip()
        if result_text:
            return result_text
        return (
            "I could not generate a response from the available specialist context. "
            "Please try rephrasing your request."
        )

    _emit_progress(
        progress_callback,
        {
            "type": "status",
            "source": "specialist",
            "status": "running",
            "label": f"{specialist_name} is working",
            "agent_name": specialist_name,
        },
    )

    stream_result = Runner.run_streamed(specialist_agent, input=input_text)
    async for event in stream_result.stream_events():
        if event.type == "agent_updated_stream_event":
            new_agent = getattr(event, "new_agent", None)
            new_agent_name = getattr(new_agent, "name", None)
            if isinstance(new_agent_name, str) and new_agent_name.strip():
                _emit_progress(
                    progress_callback,
                    {
                        "type": "agent_update",
                        "source": "specialist",
                        "agent_name": new_agent_name.strip(),
                        "label": f"Active agent: {new_agent_name.strip()}",
                    },
                )
            continue

        if event.type != "run_item_stream_event":
            continue

        item = getattr(event, "item", None)
        item_type = getattr(item, "type", None)
        if item is None or not isinstance(item_type, str):
            continue

        if item_type == "tool_call_item":
            tool_name = _extract_tool_name(item)
            _emit_progress(
                progress_callback,
                {
                    "type": "tool_call_started",
                    "source": "specialist",
                    "agent_name": specialist_name,
                    "tool_name": tool_name,
                    "tool_call_id": _extract_tool_call_id(item),
                    "label": f"Running {tool_name}",
                },
            )
            continue

        if item_type == "tool_call_output_item":
            tool_name = _extract_tool_name(item)
            _emit_progress(
                progress_callback,
                {
                    "type": "tool_call_finished",
                    "source": "specialist",
                    "agent_name": specialist_name,
                    "tool_name": tool_name,
                    "tool_call_id": _extract_tool_call_id(item),
                    "label": f"Finished {tool_name}",
                },
            )

    result_text = _extract_result_text(stream_result).strip()
    if not result_text:
        result_text = (
            "I could not generate a response from the available specialist context. "
            "Please try rephrasing your request."
        )
    return result_text


def build_specialist_tools(
    *,
    db: Session,
    user_id: int,
    student_id: int,
    chat_session_id: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[Any]:
    alias_ctx = _get_alias_context(db, student_id)
    student_read_agent = create_student_read_agent(
        db=db,
        user_id=user_id,
        student_id=student_id,
    )
    progress_notes_agent = create_progress_notes_agent(
        db=db,
        user_id=user_id,
        student_id=student_id,
        chat_session_id=chat_session_id,
    )
    web_research_agent = create_web_research_agent()

    @function_tool
    async def student_read_specialist(question: str) -> str:
        """
        Ask the read-only student specialist to answer a student-data question.
        """
        sanitized_question = redact_student_name_from_value(question, alias_ctx)
        return await _run_specialist_with_progress(
            specialist_name="StudentReadSpecialist",
            specialist_agent=student_read_agent,
            input_text=sanitized_question,
            progress_callback=progress_callback,
        )

    @function_tool
    async def progress_notes_specialist(request: str) -> str:
        """
        Ask the progress-notes specialist to draft or refine a note.
        """
        sanitized_request = redact_student_name_from_value(request, alias_ctx)
        return await _run_specialist_with_progress(
            specialist_name="ProgressNotesSpecialist",
            specialist_agent=progress_notes_agent,
            input_text=sanitized_request,
            progress_callback=progress_callback,
        )

    @function_tool
    async def web_research_specialist(request: str) -> str:
        """
        Ask the web research specialist to perform non-student-specific web research.
        """
        sanitized_request = _sanitize_for_web_research(request, alias_ctx)
        return await _run_specialist_with_progress(
            specialist_name="WebResearchSpecialist",
            specialist_agent=web_research_agent,
            input_text=sanitized_request,
            progress_callback=progress_callback,
        )

    return [student_read_specialist, progress_notes_specialist, web_research_specialist]


def build_general_specialist_tools(
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> list[Any]:
    web_research_agent = create_web_research_agent()

    @function_tool
    async def web_research_specialist(request: str) -> str:
        """
        Ask the web research specialist to perform public web research in general-chat mode.
        """
        # General mode has no selected student context; block common student identifier formats.
        sanitized_request = re.sub(r"\bstudent[_\s-]?\d+\b", "a student", request, flags=re.IGNORECASE)
        return await _run_specialist_with_progress(
            specialist_name="WebResearchSpecialist",
            specialist_agent=web_research_agent,
            input_text=sanitized_request,
            progress_callback=progress_callback,
        )

    return [web_research_specialist]

