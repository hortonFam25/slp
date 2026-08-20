from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from sqlalchemy.orm import Session

from agents import Agent

from app.ai.privacy import build_alias_context
from app.ai.factory import create_agent
from app.ai.tools.read_tools import build_read_tools
from app.ai.tools.write_tools import build_write_tools
from app.models.student import Student


@lru_cache(maxsize=1)
def _load_progress_note_template() -> str:
    template_path = Path(__file__).resolve().parent.parent / "templates" / "progress_note_template.md"
    if not template_path.exists():
        return (
            "Progress Note Template (fallback):\n"
            "- Session Overview\n"
            "- Goals/Objectives Addressed\n"
            "- Student Performance Data\n"
            "- Clinical Impression\n"
            "- Next Steps"
        )
    return template_path.read_text(encoding="utf-8")


def _get_alias_context(db: Session, student_id: int):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError("Student not found")
    return build_alias_context(
        student_id=student.id,
        first_name=student.first,
        last_name=student.last,
    )


def create_progress_notes_agent(
    *,
    db: Session,
    user_id: int,
    student_id: int,
    chat_session_id: int | None = None,
) -> Agent:
    alias_ctx = _get_alias_context(db, student_id)
    read_tools = build_read_tools(db=db, alias_ctx=alias_ctx, user_id=user_id)
    write_tools = build_write_tools(
        db=db,
        alias_ctx=alias_ctx,
        user_id=user_id,
        chat_session_id=chat_session_id,
    )
    tools = [*read_tools, *write_tools]

    progress_note_template = _load_progress_note_template()
    instructions = f"""
You are an AI assistant that helps Speech Language Pathologists (SLPs) create progress notes for their students.
You must use the tools provided to you to gather the information you need to create the progress note.

Progress notes are used to track student progress over time and are used to make decisions about student therapy. 
Your job is to create progress notes for each goal and objective in the student's year plan using therapy session data. 
Each annaul goal has one or more objectives. If there is not therapy data for a specific goal or objective please note that in the progress note.

Use the tools below to gather the information you need to create the progress note:
1) get_student_year_plan_context
2) get_student_therapy_dataset
3) get_prior_saved_progress_notes

You can call tools multiple times as needed to gather information. 

Use only student aliases or IDs in your reasoning and outputs.
Evaluate progress over time for each objective across the school year. Average any numeric data for specific objectives over the time period.
Do not regurgitate session notes; provide evaluative statements with evidence trends.

Use must use the following template which includes formatting and instruction guidance for the progress notes:
{progress_note_template}
""".strip()
    return create_agent(
        name="ProgressNotesSpecialist",
        instructions=instructions,
        tools=tools,
    )

