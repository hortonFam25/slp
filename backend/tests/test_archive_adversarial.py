"""Adversarial probes at the archive/restore framework.

`test_archive_filtering.py` walks the REPOSITORIES. `test_archive_restore.py`
walks the SERVICE and the two blessed surfaces. This file attacks the paths
that go round both of them:

* the AI chat read tools (`app/ai/tools/read_tools.py`), which query the ORM
  directly and never touch a repository -- the context an assistant is handed
  when a therapist asks it to write a progress note;
* the scheduling service and the `TimeBlock` model properties, which build
  appointment payloads and group rosters out of raw relationships;
* the MCP `get_student` detail path, which shares a repository method with the
  React student page and inherited its "archived students ARE returned" default;
* `PUT /api/students/{id}` with `is_archived`, the pre-archive-framework write
  path that set the flag with no event and no cascade;
* two sessions restoring the same event at the same time.

Every test here failed before the fix in the same commit. The invariants under
attack are the four the framework claims:

    A. archived data never appears in a default read path
    B. restore resurrects exactly the event's cascade set, never more
    C. no path hard-deletes clinical data
    D. MCP output carries no names
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db(client):
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def user(db):
    from app.models.user import User

    row = User(
        external_auth_id="pytest-archive-adversarial",
        email="archive-adversarial@example.invalid",
        display_name="Adversarial Tester",
        role="therapist",
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row.id


@pytest.fixture
def tree(db):
    """One student with two goals, objectives, entries, a session and a slot."""
    from app.models.appointment import Appointment
    from app.models.goal_category import GoalCategory
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.session_objective import SessionObjective
    from app.models.student import Student
    from app.models.therapy_session import TherapySession

    category = (
        db.query(GoalCategory).filter(GoalCategory.name == "Adversarial").first()
    )
    if category is None:
        category = GoalCategory(name="Adversarial")
        db.add(category)
        db.flush()

    student = Student(
        student_alias="pending",
        first="Adversa",
        last="Probeworth",
        grade_level="4",
        enrollment_status="Active",
    )
    db.add(student)
    db.flush()
    student.student_alias = f"student_{student.id}"

    goals, objectives, entries = [], [], []
    for number in ("1", "2"):
        goal = IEPGoal(
            student_id=student.id,
            goal_category_id=category.id,
            goal_number=number,
            goal_description=f"Adversarial goal {number}",
            target_criteria="80%",
            goal_status="Active",
            start_date=date(2026, 1, 5),
        )
        db.add(goal)
        db.flush()
        goals.append(goal)
        objective = GoalObjective(
            goal_id=goal.id,
            objective_number=1,
            objective_description=f"Adversarial objective of goal {number}",
        )
        db.add(objective)
        db.flush()
        objectives.append(objective)
        entry = ObjectiveProgressEntry(
            objective_id=objective.id,
            progress_date=date(2026, 2, 10),
            progress_on_objective=f"Entry for goal {number}",
            therapist_initials="AP",
        )
        db.add(entry)
        db.flush()
        entries.append(entry)

    sessions = []
    for index, number in enumerate(("1", "2")):
        row = TherapySession(
            student_id=student.id,
            session_date=datetime(2026, 2, 10 + index, 10, 0, 0),
            session_type="individual",
            status="completed",
            actual_duration_minutes=30,
            created_from="manual",
            session_notes=f"Adversarial session {number}",
        )
        db.add(row)
        db.flush()
        db.add(
            SessionObjective(
                therapy_session_id=row.id,
                objective_id=objectives[index].id,
                goal_id=goals[index].id,
                planned=True,
                worked_on=True,
                session_notes=f"Worked in session {number}",
            )
        )
        sessions.append(row)

    appointment = Appointment(
        student_id=student.id,
        start_datetime=datetime(2026, 6, 10, 9, 0, 0),
        end_datetime=datetime(2026, 6, 10, 9, 30, 0),
        appointment_type="individual",
        status="scheduled",
    )
    db.add(appointment)
    db.commit()

    return {
        "student": student.id,
        "goals": [goal.id for goal in goals],
        "objectives": [objective.id for objective in objectives],
        "entries": [entry.id for entry in entries],
        "sessions": [row.id for row in sessions],
        "appointment": appointment.id,
        "first": student.first,
        "last": student.last,
    }


@pytest.fixture
def alias_ctx(tree):
    from app.ai.privacy import build_alias_context

    return build_alias_context(tree["student"], tree["first"], tree["last"])


@pytest.fixture
def read_tools(db, user, alias_ctx):
    """The AI chat read tools as plain callables, keyed by name."""
    from app.ai.tools.read_tools import build_read_tool_impls

    return {
        impl.__name__: impl
        for impl in build_read_tool_impls(db=db, alias_ctx=alias_ctx, user_id=user)
    }


def _archive(db, user, entity_type, entity_id):
    from app.services import archive as archive_service

    return archive_service.archive(
        db, user_id=user, entity_type=entity_type, entity_id=entity_id
    )


def _row(db, model, row_id):
    db.expire_all()
    return db.query(model).filter(model.id == row_id).first()


# ---------------------------------------------------------------------------
# INVARIANT A -- the AI chat context builders
# ---------------------------------------------------------------------------
def test_ai_year_plan_context_hides_an_archived_goal(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_GOAL, tree["goals"][0])

    payload = read_tools["get_student_year_plan_context"]()
    returned = {goal["goal_id"] for goal in payload["annual_goals"]}

    assert tree["goals"][0] not in returned
    assert tree["goals"][1] in returned


def test_ai_year_plan_context_hides_an_archived_objective(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_OBJECTIVE, tree["objectives"][0])

    payload = read_tools["get_student_year_plan_context"]()
    by_goal = {goal["goal_id"]: goal for goal in payload["annual_goals"]}
    ids = {
        objective["objective_id"]
        for objective in by_goal[tree["goals"][0]]["objectives"]
    }

    assert tree["objectives"][0] not in ids


def test_ai_goals_and_objectives_hides_archived_rows(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_GOAL, tree["goals"][0])
    _archive(db, user, archive_service.ENTITY_OBJECTIVE, tree["objectives"][1])

    payload = read_tools["get_student_goals_and_objectives"]()
    goal_ids = {goal["goal_id"] for goal in payload["annual_goals"]}
    objective_ids = {
        objective["objective_id"]
        for goal in payload["annual_goals"]
        for objective in goal["objectives"]
    }

    assert tree["goals"][0] not in goal_ids
    assert tree["objectives"][1] not in objective_ids


def test_ai_therapy_sessions_hide_an_archived_session(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_THERAPY_SESSION, tree["sessions"][0])

    payload = read_tools["get_student_therapy_sessions"]()
    ids = {row["therapy_session_id"] for row in payload["therapy_sessions"]}

    assert tree["sessions"][0] not in ids
    assert tree["sessions"][1] in ids


def test_ai_therapy_dataset_hides_an_archived_session(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_THERAPY_SESSION, tree["sessions"][0])

    payload = read_tools["get_student_therapy_dataset"]()
    ids = {row["session_record"]["id"] for row in payload["therapy_sessions"]}

    assert tree["sessions"][0] not in ids


def test_ai_progress_snapshot_hides_work_from_an_archived_session(
    db, user, tree, read_tools
):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_THERAPY_SESSION, tree["sessions"][0])

    payload = read_tools["get_student_progress_snapshot"]()
    session_ids = {
        item["therapy_session_id"]
        for item in payload["current_therapy_objective_history"]
    }

    assert tree["sessions"][0] not in session_ids
    assert tree["sessions"][1] in session_ids


def test_ai_progress_snapshot_hides_an_archived_objective(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_OBJECTIVE, tree["objectives"][0])

    payload = read_tools["get_student_progress_snapshot"]()
    objective_ids = {
        item["objective_id"]
        for item in payload["current_therapy_objective_history"]
    }

    assert tree["objectives"][0] not in objective_ids


def test_ai_profile_refuses_an_archived_student(db, user, tree, read_tools):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    assert "error" in read_tools["get_student_profile"]()
    assert "error" in read_tools["get_student_year_plan_context"]()


def test_ai_chat_refuses_to_open_a_session_for_an_archived_student(db, user, tree):
    """The entry point, not just the tools: no chat context for a hidden child."""
    from app.services import archive as archive_service
    from app.services.ai_chat_service import AIChatService

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    service = AIChatService(db, user_id=user)
    with pytest.raises(ValueError):
        service.create_session(student_id=tree["student"])


# ---------------------------------------------------------------------------
# INVARIANT A -- scheduling payloads
# ---------------------------------------------------------------------------
@pytest.fixture
def group_block(db, tree):
    """A group time block with the tree's student and a second student on it."""
    from app.models.appointment import Appointment
    from app.models.block_assignment import BlockAssignment
    from app.models.student import Student
    from app.models.time_block import TimeBlock

    other = Student(
        student_alias="pending",
        first="Groupmate",
        last="Steady",
        grade_level="4",
        enrollment_status="Active",
    )
    db.add(other)
    db.flush()
    other.student_alias = f"student_{other.id}"

    block = TimeBlock(
        title="Adversarial group",
        start_datetime=datetime(2026, 6, 11, 9, 0, 0),
        end_datetime=datetime(2026, 6, 11, 9, 30, 0),
        max_students=4,
        status="scheduled",
    )
    db.add(block)
    db.flush()

    appointments = []
    for student_id in (tree["student"], other.id):
        db.add(
            BlockAssignment(
                time_block_id=block.id,
                student_id=student_id,
                status="assigned",
            )
        )
        appointment = Appointment(
            student_id=student_id,
            time_block_id=block.id,
            start_datetime=block.start_datetime,
            end_datetime=block.end_datetime,
            appointment_type="group",
            status="scheduled",
        )
        db.add(appointment)
        db.flush()
        appointments.append(appointment.id)

    db.commit()
    return {"block": block.id, "other": other.id, "appointments": appointments}


def test_time_block_appointment_list_hides_an_archived_appointment(
    db, user, tree, group_block
):
    from app.services import archive as archive_service
    from app.services.time_block_scheduling_service import TimeBlockSchedulingService

    _archive(
        db, user, archive_service.ENTITY_APPOINTMENT, group_block["appointments"][0]
    )

    service = TimeBlockSchedulingService(db)
    ids = {
        row.id for row in service.get_time_block_appointments(group_block["block"])
    }

    assert group_block["appointments"][0] not in ids
    assert group_block["appointments"][1] in ids


def test_time_block_appointments_route_hides_an_archived_appointment(
    client, db, user, tree, group_block
):
    from app.services import archive as archive_service

    _archive(
        db, user, archive_service.ENTITY_APPOINTMENT, group_block["appointments"][0]
    )

    response = client.get(
        f"/api/scheduling/time-blocks/{group_block['block']}/appointments"
    )
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}

    assert group_block["appointments"][0] not in ids
    assert group_block["appointments"][1] in ids


def test_group_roster_property_drops_an_archived_student(db, user, tree, group_block):
    """`TimeBlock.assigned_students` feeds counts, rosters and time slots."""
    from app.models.time_block import TimeBlock
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    block = _row(db, TimeBlock, group_block["block"])
    roster = {student.id for student in block.assigned_students}

    assert tree["student"] not in roster
    assert group_block["other"] in roster
    assert block.current_student_count == 1
    slots = {slot["student"].id for slot in block.calculate_student_time_slots()}
    assert tree["student"] not in slots


def test_time_block_detail_route_drops_an_archived_student(
    client, db, user, tree, group_block
):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    response = client.get(f"/api/scheduling/time-blocks/{group_block['block']}")
    assert response.status_code == 200
    payload = response.json()
    ids = {row["id"] for row in payload["assigned_students"]}

    assert tree["student"] not in ids
    assert payload["current_student_count"] == 1


# ---------------------------------------------------------------------------
# INVARIANT A -- MCP
# ---------------------------------------------------------------------------
@pytest.fixture
def as_principal(db, user, tree, group_block):
    from app.mcp import auth as mcp_auth
    from app.mcp.auth import McpPrincipal

    principal = McpPrincipal(
        user_id=user,
        token_id=1,
        user_name="Adversarial Tester",
        role="therapist",
        is_admin=False,
        access_mode="enforce",
        enforce_access=True,
        allowed_student_ids=[tree["student"], group_block["other"]],
    )

    def run(fn, /, **kwargs):
        token = mcp_auth._CURRENT.set(principal)
        try:
            return fn(**kwargs)
        finally:
            mcp_auth._CURRENT.reset(token)

    return run


def _tools():
    from app.mcp.server import registered_tools

    return {tool.name: tool for tool in registered_tools()}


def test_mcp_get_student_refuses_an_archived_student(db, user, tree, as_principal):
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    with pytest.raises(ValueError):
        as_principal(_tools()["get_student"].fn, student_id=tree["student"])


def test_mcp_schedule_hides_an_archived_appointment(
    db, user, tree, group_block, as_principal
):
    from app.services import archive as archive_service

    _archive(
        db, user, archive_service.ENTITY_APPOINTMENT, group_block["appointments"][0]
    )

    schedule = as_principal(
        _tools()["get_schedule"].fn,
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    ids = {row["appointmentId"] for row in schedule["appointments"]}

    assert group_block["appointments"][0] not in ids
    assert group_block["appointments"][1] in ids


def test_mcp_schedule_group_roster_hides_an_archived_student(
    db, user, tree, group_block, as_principal
):
    """A group block's roster is built from raw block_assignments."""
    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    schedule = as_principal(
        _tools()["get_schedule"].fn,
        start_date="2026-06-01",
        end_date="2026-06-30",
    )
    blocks = {row["timeBlockId"]: row for row in schedule["timeBlocks"]}
    roster = {row["studentId"] for row in blocks[group_block["block"]]["students"]}

    assert tree["student"] not in roster
    assert group_block["other"] in roster


def test_mcp_caseload_overview_counts_only_active_records(
    db, user, tree, as_principal
):
    from app.services import archive as archive_service

    before = as_principal(_tools()["get_caseload_overview"].fn)
    _archive(db, user, archive_service.ENTITY_GOAL, tree["goals"][0])
    after = as_principal(_tools()["get_caseload_overview"].fn)

    assert after["goals"]["total"] == before["goals"]["total"] - 1


# ---------------------------------------------------------------------------
# the legacy `is_archived` write path
# ---------------------------------------------------------------------------
def test_put_student_is_archived_true_creates_an_event_and_cascades(
    client, db, user, tree
):
    """The pre-framework write path must not archive without an event.

    Before the fix this set `archived_at` on the student row alone: no event,
    so nothing could restore it, and every goal, session and appointment stayed
    ACTIVE under a student nobody could see.
    """
    from app.models.appointment import Appointment
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student
    from app.models.therapy_session import TherapySession

    response = client.put(
        f"/api/students/{tree['student']}", json={"is_archived": True}
    )
    assert response.status_code == 200
    assert response.json()["is_archived"] is True

    student = _row(db, Student, tree["student"])
    assert student.archived_at is not None
    assert student.archive_event_id is not None

    assert _row(db, IEPGoal, tree["goals"][0]).archived_at is not None
    assert _row(db, TherapySession, tree["sessions"][0]).archived_at is not None
    assert _row(db, Appointment, tree["appointment"]).archived_at is not None


def test_put_student_is_archived_true_is_a_no_op_when_already_archived(
    client, db, user, tree
):
    """The React edit form echoes the current flag on every save."""
    from app.models.student import Student

    event = _archive(db, user, "student", tree["student"])

    response = client.put(
        f"/api/students/{tree['student']}",
        json={"is_archived": True, "grade_level": "5"},
    )
    assert response.status_code == 200

    student = _row(db, Student, tree["student"])
    assert student.archive_event_id == event.id
    assert student.grade_level == "5"


def test_put_student_is_archived_false_restores_the_whole_event(
    client, db, user, tree
):
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student

    _archive(db, user, "student", tree["student"])

    response = client.put(
        f"/api/students/{tree['student']}", json={"is_archived": False}
    )
    assert response.status_code == 200

    assert _row(db, Student, tree["student"]).archived_at is None
    assert _row(db, IEPGoal, tree["goals"][0]).archived_at is None


def test_put_student_is_archived_false_leaves_an_older_event_alone(
    client, db, user, tree
):
    """Invariant B through the legacy path: unarchive is not a global undo."""
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student

    _archive(db, user, "goal", tree["goals"][0])
    _archive(db, user, "student", tree["student"])

    client.put(f"/api/students/{tree['student']}", json={"is_archived": False})

    assert _row(db, Student, tree["student"]).archived_at is None
    assert _row(db, IEPGoal, tree["goals"][0]).archived_at is not None
    assert _row(db, IEPGoal, tree["goals"][1]).archived_at is None


# ---------------------------------------------------------------------------
# INVARIANT B -- restore run twice
# ---------------------------------------------------------------------------
def test_a_second_concurrent_restore_of_one_event_fails_cleanly(db, user, tree):
    """Two sessions, one event. Exactly one restore may win.

    Both read `restored_at IS NULL` before either writes -- the interleaving a
    single-process test can reproduce faithfully because sqlite gives each
    Session its own connection. The loser must raise, not report a successful
    restore of rows the winner had already put back.
    """
    from app.db.database import SessionLocal
    from app.models.archive_event import ArchiveEvent
    from app.services import archive as archive_service

    event = _archive(db, user, archive_service.ENTITY_GOAL, tree["goals"][0])

    first = SessionLocal()
    second = SessionLocal()
    try:
        # The loser loads the event FIRST and holds the instance. This is the
        # bad case: SQLAlchemy will hand the same object back from its identity
        # map on the re-read inside `restore`, with `restored_at` still NULL,
        # so the Python-level guard sees an un-restored event.
        held = (
            second.query(ArchiveEvent).filter(ArchiveEvent.id == event.id).one()
        )
        assert held.restored_at is None

        result = archive_service.restore(first, user_id=user, event_id=event.id)
        assert result["totalRows"] > 0

        with pytest.raises(archive_service.AlreadyRestoredError):
            archive_service.restore(second, user_id=user, event_id=event.id)

        # And the winner's stamp is the one that stands.
        second.expire_all()
        assert (
            second.query(ArchiveEvent)
            .filter(ArchiveEvent.id == event.id)
            .one()
            .restored_by_user_id
            == user
        )
    finally:
        first.close()
        second.close()


def test_restoring_an_already_restored_event_never_reports_rows(db, user, tree):
    from app.services import archive as archive_service

    event = _archive(db, user, archive_service.ENTITY_GOAL, tree["goals"][0])
    archive_service.restore(db, user_id=user, event_id=event.id)

    with pytest.raises(archive_service.AlreadyRestoredError):
        archive_service.restore(db, user_id=user, event_id=event.id)


# ---------------------------------------------------------------------------
# admin coherence
# ---------------------------------------------------------------------------
def test_an_admin_can_list_the_events_they_are_allowed_to_restore(db, user, tree):
    """`restore_archived` lets an admin cross user lines; listing must too.

    Otherwise an admin can restore only by guessing event ids -- a blind write
    with no way to see what it would bring back.
    """
    from app.mcp import auth as mcp_auth
    from app.mcp.auth import McpPrincipal
    from app.models.user import User
    from app.services import archive as archive_service

    other_user = User(
        external_auth_id="pytest-archive-other-owner",
        email="archive-other@example.invalid",
        display_name="Other Therapist",
        role="therapist",
        is_active=True,
    )
    db.add(other_user)
    db.commit()

    event = archive_service.archive(
        db,
        user_id=other_user.id,
        entity_type=archive_service.ENTITY_GOAL,
        entity_id=tree["goals"][0],
    )

    admin = McpPrincipal(
        user_id=user,
        token_id=2,
        user_name="Admin Tester",
        role="admin",
        is_admin=True,
        access_mode="enforce",
        enforce_access=True,
        allowed_student_ids=[],
    )
    token = mcp_auth._CURRENT.set(admin)
    try:
        rows = _tools()["list_archive_events"].fn()
    finally:
        mcp_auth._CURRENT.reset(token)

    listed = {row["eventId"]: row for row in rows}
    assert event.id in listed
    assert listed[event.id]["userId"] == other_user.id
    # Flagged, so an admin can tell somebody else's undo history from their own.
    assert listed[event.id]["ownedByCaller"] is False


def test_a_therapist_still_sees_only_their_own_events(db, user, tree, as_principal):
    from app.models.user import User
    from app.services import archive as archive_service

    other_user = User(
        external_auth_id="pytest-archive-other-owner-2",
        email="archive-other-2@example.invalid",
        display_name="Other Therapist Two",
        role="therapist",
        is_active=True,
    )
    db.add(other_user)
    db.commit()

    event = archive_service.archive(
        db,
        user_id=other_user.id,
        entity_type=archive_service.ENTITY_GOAL,
        entity_id=tree["goals"][0],
    )

    rows = as_principal(_tools()["list_archive_events"].fn)
    assert event.id not in {row["eventId"] for row in rows}


# ---------------------------------------------------------------------------
# INVARIANT D -- no names in archive output
# ---------------------------------------------------------------------------
def test_archive_event_listing_carries_no_student_name(db, user, tree, as_principal):
    import json

    from app.services import archive as archive_service

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    blob = json.dumps(as_principal(_tools()["list_archive_events"].fn), default=str)
    assert tree["first"] not in blob
    assert tree["last"] not in blob
    assert f"student_{tree['student']}" in blob


# ---------------------------------------------------------------------------
# INVARIANT C -- the import path does not create a second record for a
# returning child, and does not delete anything of theirs
# ---------------------------------------------------------------------------
def test_commit_import_refuses_a_uic_owned_by_an_archived_student(db, user, tree):
    """The validate report says "restore"; commit must actually refuse."""
    import json

    from app.models.import_batch import ImportBatch, ImportRow
    from app.models.student import Student
    from app.services import archive as archive_service
    from app.services import blind_import

    student = _row(db, Student, tree["student"])
    student.uic = "ADVERSARIAL-UIC-1"
    db.commit()

    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    batch = ImportBatch(
        user_id=user,
        status=blind_import.STATUS_UPLOADED,
        sheet_count=1,
    )
    db.add(batch)
    db.flush()
    header = ["first", "last", "uic"]
    db.add(
        ImportRow(
            batch_id=batch.id,
            sheet_name="Sheet1",
            row_index=1,
            cells_json=json.dumps(header),
        )
    )
    db.add(
        ImportRow(
            batch_id=batch.id,
            sheet_name="Sheet1",
            row_index=2,
            cells_json=json.dumps(["Adversa", "Probeworth", "ADVERSARIAL-UIC-1"]),
        )
    )
    db.commit()

    blind_import.set_mapping(
        db,
        batch,
        {
            "sheet": "Sheet1",
            "header_row": 1,
            "data_start_row": 2,
            "columns": {"A": "first_name", "B": "last_name", "C": "uic"},
        },
        (),
    )
    result = blind_import.commit(db, batch, user_id=user, confirm=True)

    assert result["committed"] is False
    assert result["issueCounts"].get("duplicate_uic_existing") == 1
    # Nothing new was created beside the archived child.
    assert (
        db.query(Student).filter(Student.uic == "ADVERSARIAL-UIC-1").count() == 1
    )


def test_removing_a_student_from_a_block_deletes_no_appointment(
    client, db, user, tree, group_block
):
    """Invariant C on the auto-rescheduling path."""
    from app.models.appointment import Appointment

    before = db.query(Appointment).count()
    response = client.delete(
        f"/api/scheduling/time-blocks/{group_block['block']}"
        f"/students/{tree['student']}"
    )
    assert response.status_code == 200
    assert db.query(Appointment).count() == before


def test_cancelling_a_block_schedule_deletes_no_appointment(
    client, db, user, group_block
):
    from app.models.appointment import Appointment

    before = db.query(Appointment).count()
    response = client.delete(
        f"/api/scheduling/time-blocks/{group_block['block']}/schedule",
        params={"cancel_future_only": False},
    )
    assert response.status_code == 200
    assert db.query(Appointment).count() == before


# ---------------------------------------------------------------------------
# the two legacy CSV importers
# ---------------------------------------------------------------------------
def test_goals_import_will_not_hang_a_live_goal_off_an_archived_student(
    db, user, tree
):
    """An active goal under a hidden student is exactly what restore forbids.

    Both importers resolve a student by UIC, and `get_student_by_uic` sees the
    archive on purpose (the row owns a UNIQUE identifier). Before the fix the
    goals importer took that archived student and created a brand new ACTIVE
    goal under them: reachable from no list, counted by no total, and swept
    into somebody else's event the next time the student was archived.
    """
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student
    from app.services import archive as archive_service
    from app.services.goals_import_service import GoalsImportService

    student = _row(db, Student, tree["student"])
    student.uic = "GOALS-IMPORT-UIC"
    db.commit()
    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    csv_content = (
        "ID,Goal,Responsible Staff,Objective1\n"
        "GOALS-IMPORT-UIC,Imported goal for an archived child,SLP,Objective one\n"
    )
    result = GoalsImportService(db).import_goals_from_csv(csv_content=csv_content)

    assert result.successful_imports == 0
    assert result.failed_imports == 1
    assert "archiv" in str(result.errors).lower()
    assert (
        db.query(IEPGoal)
        .filter(
            IEPGoal.student_id == tree["student"],
            IEPGoal.archived_at.is_(None),
        )
        .count()
        == 0
    )


def test_student_csv_import_will_not_silently_edit_an_archived_student(
    db, user, tree
):
    from app.models.student import Student
    from app.services import archive as archive_service
    from app.services.csv_import_service import CSVImportService

    student = _row(db, Student, tree["student"])
    student.uic = "STUDENT-IMPORT-UIC"
    db.commit()
    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    csv_content = (
        "first,last,uic,grade_level\n"
        "Rewritten,Overwritten,STUDENT-IMPORT-UIC,9\n"
    )
    result = CSVImportService(db).import_students_from_csv(
        csv_content=csv_content, skip_duplicates=False, update_existing=True
    )

    assert result.updated_existing == 0
    assert result.failed_imports == 1
    assert "archiv" in str(result.errors).lower()

    after = _row(db, Student, tree["student"])
    assert after.first == tree["first"]
    assert after.grade_level != "9"
    assert after.archived_at is not None


def test_student_csv_import_reports_an_archived_uic_as_a_duplicate_to_restore(
    db, user, tree
):
    """skip_duplicates: the row is skipped, and nothing new is created."""
    from app.models.student import Student
    from app.services import archive as archive_service
    from app.services.csv_import_service import CSVImportService

    student = _row(db, Student, tree["student"])
    student.uic = "STUDENT-SKIP-UIC"
    db.commit()
    _archive(db, user, archive_service.ENTITY_STUDENT, tree["student"])

    csv_content = "first,last,uic\nRewritten,Overwritten,STUDENT-SKIP-UIC\n"
    result = CSVImportService(db).import_students_from_csv(
        csv_content=csv_content, skip_duplicates=True, update_existing=False
    )

    assert result.successful_imports == 0
    assert db.query(Student).filter(Student.uic == "STUDENT-SKIP-UIC").count() == 1


# ---------------------------------------------------------------------------
# a series archived under ONE event comes back under ONE restore
# ---------------------------------------------------------------------------
def test_an_appointment_series_restores_as_one_event(client, db, user, tree):
    from app.models.appointment import Appointment
    from app.models.archive_event import ArchiveEvent

    series_id = "adversarial-series"
    ids = []
    future = datetime.now() + timedelta(days=30)
    for week in (0, 1, 2):
        start = future + timedelta(days=7 * week)
        row = Appointment(
            student_id=tree["student"],
            start_datetime=start,
            end_datetime=start + timedelta(minutes=30),
            appointment_type="individual",
            status="scheduled",
            series_id=series_id,
        )
        db.add(row)
        db.flush()
        ids.append(row.id)
    db.commit()

    response = client.delete(f"/api/scheduling/appointments/series/{series_id}")
    assert response.status_code == 200
    event_id = response.json()["archiveEventId"]

    for appointment_id in ids:
        assert _row(db, Appointment, appointment_id).archive_event_id == event_id

    restore = client.post(f"/api/archive/events/{event_id}/restore")
    assert restore.status_code == 200

    for appointment_id in ids:
        assert _row(db, Appointment, appointment_id).archived_at is None
    assert _row(db, ArchiveEvent, event_id).restored_at is not None


def test_restoring_a_student_whose_school_was_deactivated_still_works(
    client, db, user, tree
):
    """Schools and teachers are soft-deleted, so a restore has FK targets."""
    from app.models.school import School
    from app.models.student import Student

    school = School(name="Adversarial Elementary", is_active=True)
    db.add(school)
    db.flush()
    student = _row(db, Student, tree["student"])
    student.school_id = school.id
    db.commit()

    archived = client.delete(f"/api/students/{tree['student']}")
    assert archived.status_code == 200
    event_id = archived.json()["archiveEventId"]

    assert client.delete(f"/api/schools/{school.id}").status_code == 200

    restore = client.post(f"/api/archive/events/{event_id}/restore")
    assert restore.status_code == 200
    restored = _row(db, Student, tree["student"])
    assert restored.archived_at is None
    assert restored.school_id == school.id


# ---------------------------------------------------------------------------
# the transaction boundary
# ---------------------------------------------------------------------------
def test_archive_commits_the_session_it_is_handed(db, user, tree):
    """`archive()` COMMITS. Pinned, because callers depend on knowing it.

    A route that still had unflushed writes when it called `archive()` would
    have them committed as a side effect, and a route that raised AFTER calling
    it could not roll the archive back. Every caller in the tree today
    (`routers/students.py`, `goals.py`, `objectives.py`,
    `progress_entries.py`, `therapy_sessions.py`, `scheduling.py`, the two
    repository wrappers and the MCP `archive_*` tools) makes the archive its
    LAST write for exactly that reason -- `update_student` commits its field
    changes first and archives afterwards.

    This test exists so that a change to the commit behaviour breaks something
    loud rather than quietly changing what those callers are promised.
    """
    from app.db.database import SessionLocal
    from app.models.student import Student
    from app.services import archive as archive_service

    student = _row(db, Student, tree["student"])
    student.grade_level = "11"  # pending, deliberately not committed

    archive_service.archive(
        db,
        user_id=user,
        entity_type=archive_service.ENTITY_GOAL,
        entity_id=tree["goals"][0],
    )

    other = SessionLocal()
    try:
        assert (
            other.query(Student).filter(Student.id == tree["student"]).one().grade_level
            == "11"
        )
    finally:
        other.close()


# ---------------------------------------------------------------------------
# counts computed in Python off raw relationships
# ---------------------------------------------------------------------------
def test_session_progress_entry_count_ignores_archived_entries(db, user, tree):
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.therapy_session import TherapySession
    from app.services import archive as archive_service

    entry = _row(db, ObjectiveProgressEntry, tree["entries"][0])
    entry.therapy_session_id = tree["sessions"][0]
    db.commit()

    assert _row(db, TherapySession, tree["sessions"][0]).progress_entries_count == 1

    _archive(db, user, archive_service.ENTITY_PROGRESS_ENTRY, tree["entries"][0])

    assert _row(db, TherapySession, tree["sessions"][0]).progress_entries_count == 0


def test_objective_progress_properties_ignore_archived_entries(db, user, tree):
    """`latest_progress_entry` / `progress_count` filter in Python.

    Under a repository read they are already safe -- `with_loader_criteria`
    keeps archived entries out of the loaded collection. They are NOT safe
    under a lazy load from a relationship nobody attached criteria to, which is
    how every non-repository path reaches an objective, so the filter is
    repeated on the property itself.
    """
    from app.models.goal_objective import GoalObjective
    from app.services import archive as archive_service

    objective = _row(db, GoalObjective, tree["objectives"][0])
    assert objective.progress_count == 1
    assert objective.latest_progress_entry is not None

    _archive(db, user, archive_service.ENTITY_PROGRESS_ENTRY, tree["entries"][0])

    objective = _row(db, GoalObjective, tree["objectives"][0])
    assert objective.progress_count == 0
    assert objective.latest_progress_entry is None
