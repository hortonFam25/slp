"""Regression tests for :mod:`app.repositories.time_block_repository`.

These exercise the repository directly against a throwaway sqlite database
rather than through the HTTP layer — the bug under test is a module-level name
resolution failure, and a unit-level call is the shortest path to it.

Background (the bug this file was written for)
----------------------------------------------
``TimeBlockRepository`` referenced ``Appointment`` from six different methods
but imported it *locally inside five of them*. ``remove_student_with_auto_
rescheduling`` was the sixth — it used the name without ever importing it, and
the module had no top-level import either. Any call that reached the update
loop (i.e. one where the block still had at least one other student assigned
after the removal) died with ``NameError: name 'Appointment' is not defined``.

The route ``DELETE /time-blocks/{id}/students/{id}`` defaults
``auto_update_appointments`` to ``True``, so this was reachable in production.

The fix moved the import to the file header and deleted the five redundant
per-method copies. ``test_remove_student_with_auto_rescheduling_updates_
remaining_appointments`` fails with that ``NameError`` against the old code.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def repo_session(db_path):
    """A Session bound to the same sqlite file the app's fixtures create.

    Depends on ``client`` indirectly via ``db_path`` only for the path; the
    tables are created here so this module can run in isolation.
    """
    import app.models  # noqa: F401  — registers every mapper on Base.metadata
    from app.db.base import Base
    from app.db.database import engine
    from sqlalchemy.orm import sessionmaker

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_block_with_two_students(session, *, title: str):
    """Create a teacher, school, two students, a time block and two appointments.

    Returns ``(time_block_id, student_to_remove_id, remaining_student_id)``.
    """
    from app.models.appointment import Appointment
    from app.models.block_assignment import BlockAssignment
    from app.models.school import School
    from app.models.student import Student
    from app.models.teacher import Teacher
    from app.models.time_block import TimeBlock

    now = datetime(2026, 3, 2, 9, 0, 0)

    school = School(name=f"{title} Elementary")
    teacher = Teacher(first_name="Reg", last_name="Test")
    session.add_all([school, teacher])
    session.flush()

    students = []
    for idx in range(2):
        student = Student(
            student_alias=f"{title}-stu-{idx}",
            first=f"First{idx}",
            last=f"Last{idx}",
        )
        session.add(student)
        students.append(student)
    session.flush()

    block = TimeBlock(
        teacher_id=teacher.id,
        school_id=school.id,
        start_datetime=now,
        end_datetime=now + timedelta(minutes=60),
        block_type="group_therapy",
        title=title,
        status="active",
        created_date=now,
        modified_date=now,
    )
    session.add(block)
    session.flush()

    for idx, student in enumerate(students):
        session.add(
            BlockAssignment(
                time_block_id=block.id,
                student_id=student.id,
                status="assigned",
                assignment_date=now,
                created_date=now,
                modified_date=now,
            )
        )
        session.add(
            Appointment(
                student_id=student.id,
                teacher_id=teacher.id,
                school_id=school.id,
                time_block_id=block.id,
                start_datetime=now + timedelta(minutes=30 * idx),
                end_datetime=now + timedelta(minutes=30 * (idx + 1)),
                appointment_type="group",
                status="scheduled",
                therapy_session_completed=False,
                created_date=now,
                modified_date=now,
            )
        )
    session.commit()

    return block.id, students[0].id, students[1].id


def test_remove_student_with_auto_rescheduling_updates_remaining_appointments(repo_session):
    """The regression test for the missing ``Appointment`` import.

    A block with two students; one is removed with ``auto_update_appointments``
    left at its default. Because a student remains, the method walks the
    recalculated time slots and queries ``Appointment`` — the exact line that
    used to raise ``NameError``.
    """
    from app.models.appointment import Appointment
    from app.repositories.time_block_repository import TimeBlockRepository

    block_id, removed_id, remaining_id = _seed_block_with_two_students(
        repo_session, title="AutoReschedule"
    )

    repo = TimeBlockRepository(repo_session)
    result = repo.remove_student_with_auto_rescheduling(block_id, removed_id)

    assert result["success"] is True
    # One student left in the block, so exactly one appointment was rescheduled.
    assert result["updated_appointments"] == 1
    assert len(result["time_slots"]) == 1
    assert result["time_slots"][0]["student"].id == remaining_id

    # The remaining student's appointment now spans the whole block: sole
    # occupant of a 60-minute block gets the full 60 minutes from the start.
    remaining_appt = (
        repo_session.query(Appointment)
        .filter(
            Appointment.time_block_id == block_id,
            Appointment.student_id == remaining_id,
        )
        .one()
    )
    assert remaining_appt.start_datetime == datetime(2026, 3, 2, 9, 0, 0)
    assert remaining_appt.end_datetime == datetime(2026, 3, 2, 10, 0, 0)


def test_remove_last_student_skips_the_rescheduling_loop(repo_session):
    """The no-students-left path returns cleanly with nothing to update.

    The *second* removal is the one under test — with the block now empty,
    ``calculate_student_time_slots`` returns ``[]`` and the update loop never
    runs. (The first removal still goes through the loop, so this test also
    tripped the original ``NameError`` on its way to the case it pins.)
    """
    from app.repositories.time_block_repository import TimeBlockRepository

    block_id, first_id, second_id = _seed_block_with_two_students(
        repo_session, title="EmptyAfterRemoval"
    )

    repo = TimeBlockRepository(repo_session)
    assert repo.remove_student_with_auto_rescheduling(block_id, first_id)["success"] is True
    result = repo.remove_student_with_auto_rescheduling(block_id, second_id)

    assert result["success"] is True
    assert result["updated_appointments"] == 0
    assert result["time_slots"] == []


def test_appointment_is_importable_from_module_namespace():
    """``Appointment`` must resolve at module scope, not per-method.

    Guards the shape of the fix: if someone re-introduces a function-local
    ``from app.models.appointment import Appointment`` and drops the header
    import, this fails immediately rather than waiting for a route to hit the
    one method that lacked its own copy.
    """
    from app.models.appointment import Appointment
    from app.repositories import time_block_repository

    assert getattr(time_block_repository, "Appointment", None) is Appointment
