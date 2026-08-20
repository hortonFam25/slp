from __future__ import annotations

from sqlalchemy.orm import Session

from agents import Agent

from app.ai.privacy import build_alias_context
from app.ai.factory import create_agent
from app.ai.tools.read_tools import build_read_tools
from app.models.student import Student


def _get_alias_context(db: Session, student_id: int):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError("Student not found")
    return build_alias_context(
        student_id=student.id,
        first_name=student.first,
        last_name=student.last,
    )


def create_student_read_agent(
    *,
    db: Session,
    user_id: int,
    student_id: int,
    chat_session_id: int | None = None,
) -> Agent:
    alias_ctx = _get_alias_context(db, student_id)
    tools = build_read_tools(db=db, alias_ctx=alias_ctx, user_id=user_id)

    instructions = """
You are the student read specialist for an SLP workflow.
Answer questions using only read-only tools and the data they return.
Never invent details. If data is missing, state that clearly.
Never use or request student names in model-facing content; use aliases or IDs only.
""".strip()
    return create_agent(
        name="StudentReadSpecialist",
        instructions=instructions,
        tools=tools,
    )

