"""The archive filter, asserted one repository method at a time.

WHY THIS FILE IS SHAPED LIKE A LIST AND NOT LIKE A LOOP OVER THE CODE
---------------------------------------------------------------------
Archiving only works if EVERY read path hides archived rows. One method that
forgets is not a cosmetic bug: it is an archived child reappearing on a
schedule, in a progress report, or in a caseload count -- which is the failure
this whole feature exists to prevent, showing up in the one place nobody looks.

So the methods are ENUMERATED here by hand, and `test_every_list_method_is_covered`
compares that enumeration against the live repository classes. A new public
read method on an archivable repository fails this file until somebody writes
down what it does with archived rows.

    >>> LOUD NOTICE TO WHOEVER ADDS THE NEXT LIST METHOD <<<
    Add it to CASES below with a seeded active row and a seeded archived one.
    If it legitimately must see archived rows (deduplication, the archive
    screens, an unarchive path), add it to SEES_ARCHIVED_BY_DESIGN with the
    reason. Do not add it to EXEMPT without one.

Each case seeds ONE active row and ONE archived row of the same kind, calls the
method, and asserts the archived id is absent by default and present with
`include_archived=True`.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta

import pytest


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db(client):
    """A session against the suite's throwaway sqlite file.

    Depends on ``client`` only for its side effect: the app's startup handler is
    what runs ``create_all``.
    """
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def world(db):
    """Two of everything: one active, one archived, per archivable entity.

    The archived half goes through `app.services.archive` rather than being
    hand-stamped, so what these assertions exercise is the same write path
    production uses -- and the same cascade. That is why the archived goal's
    objective and entry are already archived when their own cases run: they were
    swept in by their parent, which is exactly the state a filter has to cope
    with.
    """
    from app.models.appointment import Appointment
    from app.models.block_assignment import BlockAssignment
    from app.models.goal_category import GoalCategory
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.school import School
    from app.models.student import Student
    from app.models.teacher import Teacher
    from app.models.therapy_session import TherapySession
    from app.models.time_block import TimeBlock
    from app.models.user import User
    from app.services import archive as archive_service

    school = School(name="Filtering Elementary", district="Filtering ISD")
    teacher = Teacher(first_name="Filtra", last_name="Testerson", title="Teacher")
    category = GoalCategory(name="Articulation (filtering-test)")
    user = User(
        external_auth_id="pytest-archive-filtering",
        email="filtering@example.invalid",
        display_name="Filtering Tester",
        role="therapist",
        is_active=True,
    )
    db.add_all([school, teacher, category, user])
    db.flush()

    def make_student(tag: str) -> Student:
        student = Student(
            student_alias=f"pending-{tag}",
            first=f"Active{tag}",
            last=f"Filtering{tag}",
            uic=f"UICFILTER{tag}",
            grade_level="4",
            enrollment_status="Active",
            school_id=school.id,
            teacher_id=teacher.id,
            case_manager_id=teacher.id,
        )
        db.add(student)
        db.flush()
        student.student_alias = f"student_{student.id}"
        return student

    def make_goal(student: Student, number: str) -> IEPGoal:
        goal = IEPGoal(
            student_id=student.id,
            goal_category_id=category.id,
            goal_number=number,
            goal_description=f"Goal {number} for {student.student_alias}",
            target_criteria="80% across 3 sessions",
            goal_status="Active",
            start_date=date(2026, 1, 5),
            end_date=date(2020, 1, 5),  # in the past: get_overdue_goals sees it
        )
        db.add(goal)
        db.flush()
        return goal

    def make_objective(goal: IEPGoal, number: int) -> GoalObjective:
        objective = GoalObjective(
            goal_id=goal.id,
            objective_number=number,
            objective_description=f"Objective {number} under goal {goal.id}",
            progress_status="In Progress",
            schedule_frequency="weekly",
        )
        db.add(objective)
        db.flush()
        return objective

    def make_entry(objective: GoalObjective, day: int) -> ObjectiveProgressEntry:
        entry = ObjectiveProgressEntry(
            objective_id=objective.id,
            progress_date=date(2026, 2, day),
            progress_on_objective="8/10 trials",
            progress_comments="Steady",
            therapist_initials="FT",
        )
        db.add(entry)
        db.flush()
        return entry

    when = datetime(2026, 3, 4, 10, 0, 0)

    def make_session(student: Student, hour: int, status: str = "completed") -> TherapySession:
        row = TherapySession(
            student_id=student.id,
            session_date=when.replace(hour=hour),
            start_time=when.replace(hour=hour),
            end_time=when.replace(hour=hour, minute=30),
            planned_duration_minutes=30,
            actual_duration_minutes=30,
            session_type="individual",
            status=status,
            follow_up_needed=True,
            created_from="manual",
        )
        db.add(row)
        db.flush()
        return row

    def make_appointment(student: Student, hour: int, block=None) -> Appointment:
        appointment = Appointment(
            student_id=student.id,
            teacher_id=teacher.id,
            school_id=school.id,
            time_block_id=block.id if block else None,
            start_datetime=when.replace(hour=hour),
            end_datetime=when.replace(hour=hour, minute=30),
            appointment_type="individual",
            status="scheduled",
            series_id="filtering-series",
            location="Room 1",
        )
        db.add(appointment)
        db.flush()
        return appointment

    def make_block(title: str, hour: int) -> TimeBlock:
        block = TimeBlock(
            teacher_id=teacher.id,
            school_id=school.id,
            start_datetime=when.replace(hour=hour),
            end_datetime=when.replace(hour=hour, minute=45),
            block_type="group_therapy",
            title=title,
            max_students=6,
            status="active",
        )
        db.add(block)
        db.flush()
        return block

    active_student = make_student("A")
    archived_student = make_student("Z")

    active_goal = make_goal(active_student, "1")
    archived_goal = make_goal(active_student, "2")

    active_objective = make_objective(active_goal, 1)
    archived_objective = make_objective(active_goal, 2)

    active_entry = make_entry(active_objective, 10)
    archived_entry = make_entry(active_objective, 11)

    active_session = make_session(active_student, 9)
    archived_session = make_session(active_student, 11)

    active_block = make_block("Active block", 13)
    archived_block = make_block("Archived block", 14)

    active_appointment = make_appointment(active_student, 15)
    archived_appointment = make_appointment(active_student, 16)

    db.add_all(
        [
            BlockAssignment(
                time_block_id=active_block.id,
                student_id=active_student.id,
                status="assigned",
            ),
            BlockAssignment(
                time_block_id=active_block.id,
                student_id=archived_student.id,
                status="assigned",
            ),
        ]
    )
    db.commit()

    ids = {
        "user": user.id,
        "school": school.id,
        "teacher": teacher.id,
        "category": category.id,
        "active_student": active_student.id,
        "archived_student": archived_student.id,
        "active_goal": active_goal.id,
        "archived_goal": archived_goal.id,
        "active_objective": active_objective.id,
        "archived_objective": archived_objective.id,
        "active_entry": active_entry.id,
        "archived_entry": archived_entry.id,
        "active_session": active_session.id,
        "archived_session": archived_session.id,
        "active_block": active_block.id,
        "archived_block": archived_block.id,
        "active_appointment": active_appointment.id,
        "archived_appointment": archived_appointment.id,
        "series": "filtering-series",
    }

    # Archive the "archived_*" half, each under its own event, through the real
    # service. Order matters only in that a student cascade would sweep this
    # student's goals -- which is why the archived STUDENT owns nothing.
    for entity_type, key in (
        ("goal", "archived_goal"),
        ("objective", "archived_objective"),
        ("progress_entry", "archived_entry"),
        ("therapy_session", "archived_session"),
        ("appointment", "archived_appointment"),
        ("time_block", "archived_block"),
        ("student", "archived_student"),
    ):
        archive_service.archive(db, user_id=user.id, entity_type=entity_type, entity_id=ids[key])

    db.expire_all()
    return ids


# ---------------------------------------------------------------------------
# the enumeration
# ---------------------------------------------------------------------------
# (repository class, method name, kwargs builder, active id key, archived id key,
#  how to pull ids out of the result)
def _ids_of(rows):
    return {row.id for row in rows}


def _ids_of_scheduling_views(rows):
    return {row.id for row in rows}


def _id_of_single(row):
    return set() if row is None else {row.id}


CASES: list[tuple[str, str, object, str, str, object]] = [
    # -------------------------------------------------------------- students
    ("StudentRepository", "list_students", lambda w: {}, "active_student", "archived_student", _ids_of),
    (
        "StudentRepository",
        "get_students_by_case_manager",
        lambda w: {"case_manager_id": w["teacher"]},
        "active_student",
        "archived_student",
        _ids_of,
    ),
    # ----------------------------------------------------------------- goals
    ("GoalRepository", "get_goals", lambda w: {"student_id": w["active_student"]}, "active_goal", "archived_goal", _ids_of),
    (
        "GoalRepository",
        "get_student_goals",
        lambda w: {"student_id": w["active_student"]},
        "active_goal",
        "archived_goal",
        _ids_of,
    ),
    (
        "GoalRepository",
        "get_goals_by_status",
        lambda w: {"status": "Active"},
        "active_goal",
        "archived_goal",
        _ids_of,
    ),
    ("GoalRepository", "get_overdue_goals", lambda w: {}, "active_goal", "archived_goal", _ids_of),
    (
        "GoalRepository",
        "get_goal_by_id",
        lambda w: {"goal_id": w["archived_goal"]},
        None,
        "archived_goal",
        _id_of_single,
    ),
    (
        "GoalRepository",
        "get_goal_with_objectives",
        lambda w: {"goal_id": w["archived_goal"]},
        None,
        "archived_goal",
        _id_of_single,
    ),
    # ------------------------------------------------------------ objectives
    (
        "ObjectiveRepository",
        "get_objectives",
        lambda w: {"goal_id": w["active_goal"]},
        "active_objective",
        "archived_objective",
        _ids_of,
    ),
    (
        "ObjectiveRepository",
        "get_goal_objectives",
        lambda w: {"goal_id": w["active_goal"]},
        "active_objective",
        "archived_objective",
        _ids_of,
    ),
    (
        "ObjectiveRepository",
        "get_objective_by_id",
        lambda w: {"objective_id": w["archived_objective"]},
        None,
        "archived_objective",
        _id_of_single,
    ),
    # -------------------------------------------------------- progress entries
    (
        "ProgressEntryRepository",
        "get_progress_entries",
        lambda w: {"objective_id": w["active_objective"]},
        "active_entry",
        "archived_entry",
        _ids_of,
    ),
    (
        "ProgressEntryRepository",
        "get_objective_progress_entries",
        lambda w: {"objective_id": w["active_objective"]},
        "active_entry",
        "archived_entry",
        _ids_of,
    ),
    (
        "ProgressEntryRepository",
        "get_progress_entry_by_id",
        lambda w: {"entry_id": w["archived_entry"]},
        None,
        "archived_entry",
        _id_of_single,
    ),
    (
        "ProgressEntryRepository",
        "get_latest_entry_for_objective",
        # The archived entry is the LATEST by date, so an unfiltered query
        # returns it and a filtered one returns the earlier active entry --
        # which makes this case load-bearing rather than incidental.
        lambda w: {"objective_id": w["active_objective"]},
        None,
        "archived_entry",
        _id_of_single,
    ),
    # -------------------------------------------------------- therapy sessions
    (
        "TherapySessionRepository",
        "get_student_sessions",
        lambda w: {"student_id": w["active_student"]},
        "active_session",
        "archived_session",
        _ids_of,
    ),
    (
        "TherapySessionRepository",
        "get_sessions_needing_followup",
        lambda w: {},
        "active_session",
        "archived_session",
        _ids_of,
    ),
    (
        "TherapySessionRepository",
        "get_session_by_id",
        lambda w: {"session_id": w["archived_session"]},
        None,
        "archived_session",
        _id_of_single,
    ),
    (
        "TherapySessionRepository",
        "get_school_year_sessions_relative",
        lambda w: {
            "student_id": w["active_student"],
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "anchor_date": date(2026, 3, 4),
        },
        "active_session",
        "archived_session",
        _ids_of,
    ),
    # ------------------------------------------------------------ appointments
    (
        "AppointmentRepository",
        "get_appointments_by_date_range",
        lambda w: {"start_date": date(2026, 3, 4), "end_date": date(2026, 3, 4)},
        "active_appointment",
        "archived_appointment",
        _ids_of,
    ),
    (
        "AppointmentRepository",
        "get_student_appointments",
        lambda w: {"student_id": w["active_student"]},
        "active_appointment",
        "archived_appointment",
        _ids_of,
    ),
    (
        "AppointmentRepository",
        "get_teacher_appointments",
        lambda w: {"teacher_id": w["teacher"]},
        "active_appointment",
        "archived_appointment",
        _ids_of,
    ),
    (
        "AppointmentRepository",
        "get_appointments_by_series",
        lambda w: {"series_id": w["series"]},
        "active_appointment",
        "archived_appointment",
        _ids_of,
    ),
    (
        "AppointmentRepository",
        "get_appointment",
        lambda w: {"appointment_id": w["archived_appointment"]},
        None,
        "archived_appointment",
        _id_of_single,
    ),
    # ------------------------------------------------------------- time blocks
    (
        "TimeBlockRepository",
        "get_time_blocks_by_date_range",
        lambda w: {"start_date": date(2026, 3, 4), "end_date": date(2026, 3, 4)},
        "active_block",
        "archived_block",
        _ids_of,
    ),
    (
        "TimeBlockRepository",
        "get_teacher_time_blocks",
        lambda w: {"teacher_id": w["teacher"]},
        "active_block",
        "archived_block",
        _ids_of,
    ),
    (
        "TimeBlockRepository",
        "get_available_time_blocks",
        lambda w: {"start_date": date(2026, 3, 4), "end_date": date(2026, 3, 4)},
        "active_block",
        "archived_block",
        _ids_of,
    ),
    (
        "TimeBlockRepository",
        "get_time_block",
        lambda w: {"time_block_id": w["archived_block"]},
        None,
        "archived_block",
        _id_of_single,
    ),
    (
        "TimeBlockRepository",
        "get_block_students",
        lambda w: {"time_block_id": w["active_block"]},
        "active_student",
        "archived_student",
        _ids_of,
    ),
    # ------------------------------------------------------------- scheduling
    (
        "SchedulingStudentRepository",
        "get_students_for_scheduling",
        lambda w: {},
        "active_student",
        "archived_student",
        _ids_of_scheduling_views,
    ),
    (
        "SchedulingStudentRepository",
        "get_student_for_scheduling",
        lambda w: {"student_id": w["archived_student"]},
        None,
        "archived_student",
        _id_of_single,
    ),
]


def _repo(name, db):
    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.goal_repository import (
        GoalRepository,
        ObjectiveRepository,
        ProgressEntryRepository,
    )
    from app.repositories.scheduling_student_repository import SchedulingStudentRepository
    from app.repositories.student_repository import StudentRepository
    from app.repositories.therapy_session_repository import TherapySessionRepository
    from app.repositories.time_block_repository import TimeBlockRepository

    classes = {
        "AppointmentRepository": AppointmentRepository,
        "GoalRepository": GoalRepository,
        "ObjectiveRepository": ObjectiveRepository,
        "ProgressEntryRepository": ProgressEntryRepository,
        "SchedulingStudentRepository": SchedulingStudentRepository,
        "StudentRepository": StudentRepository,
        "TherapySessionRepository": TherapySessionRepository,
        "TimeBlockRepository": TimeBlockRepository,
    }
    return classes[name](db)


@pytest.mark.parametrize(
    "case", CASES, ids=[f"{c[0]}.{c[1]}" for c in CASES]
)
def test_archived_rows_are_excluded_by_default(case, db, world):
    repo_name, method_name, kwargs_for, active_key, archived_key, extract = case
    repo = _repo(repo_name, db)
    method = getattr(repo, method_name)
    kwargs = kwargs_for(world)

    default_ids = extract(method(**kwargs))
    assert world[archived_key] not in default_ids, (
        f"{repo_name}.{method_name} returned an ARCHIVED row by default. Every "
        f"read path has to filter on archived_at IS NULL."
    )
    if active_key is not None:
        assert world[active_key] in default_ids, (
            f"{repo_name}.{method_name} lost the ACTIVE row -- the filter is too "
            f"wide, which is its own kind of data loss."
        )

    with_archived = extract(method(**kwargs, include_archived=True))
    assert world[archived_key] in with_archived, (
        f"{repo_name}.{method_name} does not honour include_archived=True, so "
        f"the archived row is unreachable."
    )


# ---------------------------------------------------------------------------
# the drift gate
# ---------------------------------------------------------------------------
# Read methods that DO see archived rows on purpose, with the reason. Anything
# here has to be a decision somebody made, not a method nobody got to.
SEES_ARCHIVED_BY_DESIGN = {
    # students.uic is UNIQUE. A lookup blind to the archive reports "no such
    # UIC" and then fails on the constraint -- and the caseload import would
    # offer to re-create a child who is sitting in the archive.
    ("StudentRepository", "get_student_by_uic"),
    # The student detail page is where the Unarchive button lives, so a by-id
    # load has always returned archived students and must keep doing so.
    ("StudentRepository", "get_student_by_id"),
    # The archive screens themselves.
    ("StudentRepository", "get_archived_students"),
}

# Methods on these classes that are not read paths over an archivable entity:
# writes, helpers, and reads over tables with no archive columns.
EXEMPT_METHODS = {
    ("GoalRepository", "get_goal_categories"),  # goal_categories is not archivable
    ("TimeBlockRepository", "get_eligible_students_for_time_block"),  # asserted below
    ("TimeBlockRepository", "get_time_block_appointments_by_series"),  # asserted below
    ("TherapySessionRepository", "get_session_by_appointment_id"),  # asserted below
    ("TherapySessionRepository", "get_sessions"),  # asserted below (needs a filters obj)
    ("TherapySessionRepository", "get_session_statistics"),  # asserted below
    ("TherapySessionRepository", "get_objective_history"),  # asserted below
    ("TherapySessionRepository", "get_goal_history"),  # asserted below
    ("TherapySessionRepository", "get_active_sessions"),  # asserted below
    # asserted below. (It used to be here with no assertion at all, because the
    # method raised "minute must be in 0..59" on every input -- its slot loop
    # stepped the clock with `replace(minute=...)`. That is fixed; the loop is
    # `timedelta` now, and the filter is exercised for real. The full behaviour
    # of the method lives in tests/test_available_time_slots.py.)
    ("AppointmentRepository", "get_available_time_slots"),
    ("AppointmentRepository", "check_time_conflict"),  # asserted below
    ("TimeBlockRepository", "check_teacher_conflict"),  # asserted below
}

_ARCHIVE_AWARE_REPOS = (
    "AppointmentRepository",
    "GoalRepository",
    "ObjectiveRepository",
    "ProgressEntryRepository",
    "SchedulingStudentRepository",
    "StudentRepository",
    "TherapySessionRepository",
    "TimeBlockRepository",
)


def test_every_list_method_is_covered(db):
    """A new read method on an archive-aware repository must be written down here.

    This is the whole point of the file. The parametrised cases above prove the
    methods we know about behave; this proves we know about all of them.
    """
    covered = {(case[0], case[1]) for case in CASES}
    covered |= SEES_ARCHIVED_BY_DESIGN
    covered |= EXEMPT_METHODS

    missing = []
    for repo_name in _ARCHIVE_AWARE_REPOS:
        repo = _repo(repo_name, db)
        for method_name, member in inspect.getmembers(type(repo), inspect.isfunction):
            if method_name.startswith("_"):
                continue
            if not method_name.startswith("get") and not method_name.startswith("list"):
                continue
            if (repo_name, method_name) in covered:
                continue
            missing.append(f"{repo_name}.{method_name}")

    assert not missing, (
        "These repository read methods are not covered by this file. Add each "
        "one to CASES with a seeded active row and a seeded archived row, or to "
        "SEES_ARCHIVED_BY_DESIGN with the reason it must see the archive:\n  "
        + "\n  ".join(sorted(missing))
    )


# ---------------------------------------------------------------------------
# the methods whose signatures do not fit the parametrised shape
# ---------------------------------------------------------------------------
def test_get_sessions_filters_archived(db, world):
    from app.repositories.therapy_session_repository import TherapySessionRepository
    from app.schemas.therapy_session import TherapySessionFilters

    repo = TherapySessionRepository(db)
    filters = TherapySessionFilters(student_id=world["active_student"])

    ids = {s.id for s in repo.get_sessions(filters)}
    assert world["archived_session"] not in ids
    assert world["active_session"] in ids

    ids = {s.id for s in repo.get_sessions(filters, include_archived=True)}
    assert world["archived_session"] in ids


def test_get_active_sessions_filters_archived(db, world):
    """Seeds its own in-progress pair: the module fixture's sessions are completed."""
    from app.models.therapy_session import TherapySession
    from app.repositories.therapy_session_repository import TherapySessionRepository
    from app.services import archive as archive_service

    when = datetime(2026, 4, 1, 9, 0, 0)
    rows = []
    for hour in (9, 10):
        row = TherapySession(
            student_id=world["active_student"],
            session_date=when.replace(hour=hour),
            start_time=when.replace(hour=hour),
            session_type="individual",
            status="in_progress",
            created_from="manual",
        )
        db.add(row)
        rows.append(row)
    db.commit()
    archive_service.archive(
        db,
        user_id=world["user"],
        entity_type="therapy_session",
        entity_id=rows[1].id,
    )

    repo = TherapySessionRepository(db)
    ids = {s.id for s in repo.get_active_sessions()}
    assert rows[0].id in ids
    assert rows[1].id not in ids
    assert rows[1].id in {s.id for s in repo.get_active_sessions(include_archived=True)}


def test_get_session_by_appointment_id_filters_archived(db, world):
    from app.models.therapy_session import TherapySession
    from app.repositories.therapy_session_repository import TherapySessionRepository
    from app.services import archive as archive_service

    row = TherapySession(
        student_id=world["active_student"],
        appointment_id=world["active_appointment"],
        session_date=datetime(2026, 4, 2, 9, 0, 0),
        session_type="individual",
        status="planned",
        created_from="appointment",
    )
    db.add(row)
    db.commit()

    repo = TherapySessionRepository(db)
    assert repo.get_session_by_appointment_id(world["active_appointment"]).id == row.id

    archive_service.archive(
        db, user_id=world["user"], entity_type="therapy_session", entity_id=row.id
    )
    assert repo.get_session_by_appointment_id(world["active_appointment"]) is None
    assert (
        repo.get_session_by_appointment_id(
            world["active_appointment"], include_archived=True
        ).id
        == row.id
    )


def test_session_statistics_exclude_archived(db, world):
    """The aggregate decision, asserted rather than assumed.

    A therapist reads these numbers as "how much service was delivered". A
    session she archived is one she decided not to count.
    """
    from app.repositories.therapy_session_repository import TherapySessionRepository

    repo = TherapySessionRepository(db)
    default = repo.get_session_statistics(student_id=world["active_student"])
    everything = repo.get_session_statistics(
        student_id=world["active_student"], include_archived=True
    )
    assert everything["total_sessions"] > default["total_sessions"]


def test_objective_and_goal_history_exclude_archived_sessions(db, world):
    """A progress report may not cite a session that has been archived."""
    from app.models.session_objective import SessionObjective
    from app.repositories.therapy_session_repository import TherapySessionRepository

    db.add_all(
        [
            SessionObjective(
                therapy_session_id=world["active_session"],
                objective_id=world["active_objective"],
                goal_id=world["active_goal"],
                planned=True,
                worked_on=True,
            ),
            SessionObjective(
                therapy_session_id=world["archived_session"],
                objective_id=world["active_objective"],
                goal_id=world["active_goal"],
                planned=True,
                worked_on=True,
            ),
        ]
    )
    db.commit()

    repo = TherapySessionRepository(db)
    history = repo.get_objective_history(world["active_objective"])
    session_ids = {row.therapy_session_id for row in history}
    assert world["active_session"] in session_ids
    assert world["archived_session"] not in session_ids

    goal_history = repo.get_goal_history(world["active_goal"])
    session_ids = {row.therapy_session_id for row in goal_history["sessions"]}
    assert world["archived_session"] not in session_ids


def test_archived_appointments_do_not_hold_their_slot(db, world):
    """The scheduling decision: archiving must not be worse than deleting.

    An archived appointment that still blocked its time would leave the
    therapist unable to rebook the slot AND unable to see why.
    """
    from app.models.appointment import Appointment
    from app.repositories.appointment_repository import AppointmentRepository

    repo = AppointmentRepository(db)
    archived = db.query(Appointment).filter(
        Appointment.id == world["archived_appointment"]
    ).first()

    assert repo.check_time_conflict(
        student_id=world["active_student"],
        start_datetime=archived.start_datetime,
        end_datetime=archived.end_datetime,
    ) is False

    active = db.query(Appointment).filter(
        Appointment.id == world["active_appointment"]
    ).first()
    assert repo.check_time_conflict(
        student_id=world["active_student"],
        start_datetime=active.start_datetime,
        end_datetime=active.end_datetime,
    ) is True

    # The same decision on the other scheduling predicate: the archived
    # appointment's start comes back as an offered slot, the active one's does
    # not. The fixture books 15:00-15:30 (active) and 16:00-16:30 (archived).
    slots = repo.get_available_time_slots(
        student_id=world["active_student"],
        target_date=active.start_datetime.date(),
        duration_minutes=30,
        start_hour=15,
        end_hour=17,
    )
    assert archived.start_datetime in slots
    assert active.start_datetime not in slots


def test_archived_time_blocks_do_not_hold_the_teacher(db, world):
    from app.models.time_block import TimeBlock
    from app.repositories.time_block_repository import TimeBlockRepository

    repo = TimeBlockRepository(db)
    archived = db.query(TimeBlock).filter(TimeBlock.id == world["archived_block"]).first()
    assert repo.check_teacher_conflict(
        teacher_id=world["teacher"],
        start_datetime=archived.start_datetime,
        end_datetime=archived.end_datetime,
    ) is False


def test_eligible_students_exclude_archived(db, world):
    from app.repositories.time_block_repository import TimeBlockRepository

    repo = TimeBlockRepository(db)
    ids = {s.id for s in repo.get_eligible_students_for_time_block(world["active_block"])}
    assert world["archived_student"] not in ids


def test_time_block_series_appointments_exclude_archived(db, world):
    from app.repositories.time_block_repository import TimeBlockRepository

    repo = TimeBlockRepository(db)
    result = repo.get_time_block_appointments_by_series(world["active_block"])
    ids = {a.id for a in result["appointments"]}
    assert world["archived_appointment"] not in ids


# ---------------------------------------------------------------------------
# eager loads
# ---------------------------------------------------------------------------
def test_archived_children_do_not_ride_along_inside_a_goal(db, world):
    """The failure a query-level filter alone cannot catch.

    `get_goal_by_id` selectin-loads objectives and their entries. A
    `selectinload` does not inherit the outer WHERE, so without
    `with_loader_criteria` an archived objective disappears from
    `GET /api/objectives` and still shows up nested inside its goal.
    """
    from app.repositories.goal_repository import GoalRepository

    goal = GoalRepository(db).get_goal_by_id(world["active_goal"])
    objective_ids = {o.id for o in goal.objectives}
    assert world["active_objective"] in objective_ids
    assert world["archived_objective"] not in objective_ids

    entry_ids = {
        e.id for objective in goal.objectives for e in objective.progress_entries
    }
    assert world["active_entry"] in entry_ids
    assert world["archived_entry"] not in entry_ids

    # `expire_all` because the goal is already in this session's identity map
    # with a filtered collection attached, and a second `selectinload` does not
    # replace a collection that is already loaded.
    db.expire_all()
    everything = GoalRepository(db).get_goal_by_id(
        world["active_goal"], include_archived=True
    )
    assert world["archived_objective"] in {o.id for o in everything.objectives}
    db.expire_all()


def test_school_statistics_exclude_archived_students(db, world):
    """The aggregate on the other side: a school's headcount is a working roster."""
    from app.repositories.school_repository import SchoolRepository

    stats = SchoolRepository(db).get_school_statistics(world["school"])
    counted = sum(row["count"] for row in stats["grade_distribution"])
    assert stats["active_students"] == counted
    # The archived student is Active-enrolled and at this school; only the
    # archive keeps them out of the count.
    assert stats["active_students"] >= 1
    from app.models.student import Student

    total_at_school = (
        db.query(Student)
        .filter(Student.school_id == world["school"], Student.enrollment_status == "Active")
        .count()
    )
    assert stats["active_students"] < total_at_school


def test_uic_lookup_still_finds_an_archived_student(db, world):
    """Deduplication MUST see the archive -- see SEES_ARCHIVED_BY_DESIGN."""
    from app.repositories.student_repository import StudentRepository

    repo = StudentRepository(db)
    found = repo.get_student_by_uic("UICFILTERZ")
    assert found is not None and found.id == world["archived_student"]
    assert repo.get_student_by_uic("UICFILTERZ", include_archived=False) is None
