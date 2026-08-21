"""Archive and restore: the cascade, the faithfulness rule, and the refusals.

`test_archive_filtering.py` proves archived rows are hidden. This file proves
the archive itself behaves: that a cascade stamps the right graph under ONE
event, that restoring an event is EXACT rather than approximate, that a child
cannot be resurrected under an archived parent, and that the REST and MCP
surfaces both go through the same service.

The rule under test throughout is the one in `app/services/archive.py`:

    A cascade stamps only rows that are currently ACTIVE. A row already
    archived under an older event keeps that older event.

Everything else here follows from it. If that rule breaks, restoring a student
starts resurrecting goals somebody retired months earlier, and there is no
record anywhere that it happened.
"""

from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest

_VERSIONS = Path(__file__).resolve().parents[1] / "app" / "alembic" / "versions"

MIGRATION_PATH = _VERSIONS / "a1c4e8b60d37_add_archive_events_and_archived_columns.py"

# The archive columns did not all arrive in one revision, and there is no reason
# they should have: `a1c4e8b60d37` gave the pair to seven tables, and
# `d3f8b2a70c19` added the eighth (`student_eligibilities`) once the last hard
# DELETE in the tree turned out to be pointed at it. The drift gate below reads
# the UNION, so making a table archivable in the ORM still has to be paid for
# with a migration -- in whichever revision adds it.
ELIGIBILITY_MIGRATION_PATH = (
    _VERSIONS / "d3f8b2a70c19_add_archive_columns_to_student_eligibilities.py"
)


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
        external_auth_id="pytest-archive-restore",
        email="archive-restore@example.invalid",
        display_name="Archive Tester",
        role="therapist",
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row.id


@pytest.fixture
def tree(db, user):
    """A whole student record, built fresh for each test.

    Function-scoped on purpose: these tests archive and restore the same graph
    in incompatible ways, and sharing one would make them order-dependent --
    which is precisely the class of bug this file exists to catch.
    """
    from app.models.appointment import Appointment
    from app.models.eligibility_category import EligibilityCategory
    from app.models.goal_category import GoalCategory
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.student import Student
    from app.models.student_eligibility import StudentEligibility
    from app.models.therapy_session import TherapySession

    category = (
        db.query(GoalCategory).filter(GoalCategory.name == "Archive-test").first()
    )
    if category is None:
        category = GoalCategory(name="Archive-test")
        db.add(category)
        db.flush()

    # Shared lookup rows, created once and reused: the fixture is function
    # scoped, and `eligibility_categories.name` is UNIQUE.
    eligibility_categories = []
    for suffix in ("A", "B"):
        name = f"Archive-test eligibility {suffix}"
        row = (
            db.query(EligibilityCategory)
            .filter(EligibilityCategory.name == name)
            .first()
        )
        if row is None:
            row = EligibilityCategory(name=name, code=f"ARCH-{suffix}", display_order=90)
            db.add(row)
            db.flush()
        eligibility_categories.append(row)

    student = Student(
        student_alias="pending",
        first="Archie",
        last="Restorio",
        grade_level="3",
        enrollment_status="Active",
    )
    db.add(student)
    db.flush()
    student.student_alias = f"student_{student.id}"

    goals = []
    objectives = []
    entries = []
    for number in ("1", "2"):
        goal = IEPGoal(
            student_id=student.id,
            goal_category_id=category.id,
            goal_number=number,
            goal_description=f"Goal {number}",
            target_criteria="80%",
            goal_status="Active",
            start_date=date(2026, 1, 5),
        )
        db.add(goal)
        db.flush()
        goals.append(goal)
        for objective_number in (1, 2):
            objective = GoalObjective(
                goal_id=goal.id,
                objective_number=objective_number,
                objective_description=f"Objective {objective_number} of goal {number}",
            )
            db.add(objective)
            db.flush()
            objectives.append(objective)
            entry = ObjectiveProgressEntry(
                objective_id=objective.id,
                progress_date=date(2026, 2, 10),
                progress_on_objective="8/10",
                therapist_initials="AR",
            )
            db.add(entry)
            db.flush()
            entries.append(entry)

    session_row = TherapySession(
        student_id=student.id,
        session_date=datetime(2026, 2, 10, 10, 0, 0),
        session_type="individual",
        status="completed",
        actual_duration_minutes=30,
        created_from="manual",
    )
    db.add(session_row)
    db.flush()

    appointment = Appointment(
        student_id=student.id,
        start_datetime=datetime(2026, 6, 10, 9, 0, 0),
        end_datetime=datetime(2026, 6, 10, 9, 30, 0),
        appointment_type="individual",
        status="scheduled",
    )
    db.add(appointment)
    db.flush()

    eligibilities = []
    for index, eligibility_category in enumerate(eligibility_categories):
        row = StudentEligibility(
            student_id=student.id,
            eligibility_category_id=eligibility_category.id,
            start_date=date(2026, 1, 5 + index),
            is_primary=index == 0,
            notes="Qualifies under this category",
        )
        db.add(row)
        eligibilities.append(row)
    db.commit()

    return {
        "student": student.id,
        "goal_one": goals[0].id,
        "goal_two": goals[1].id,
        "objectives_of_goal_one": [objectives[0].id, objectives[1].id],
        "objectives_of_goal_two": [objectives[2].id, objectives[3].id],
        "entries_of_goal_one": [entries[0].id, entries[1].id],
        "entries_of_goal_two": [entries[2].id, entries[3].id],
        "session": session_row.id,
        "appointment": appointment.id,
        "eligibilities": [row.id for row in eligibilities],
    }


def _row(db, model, row_id):
    """Re-read a row from the database, past this session's identity map.

    `expire_all` because the archive service writes with bulk UPDATEs and
    `synchronize_session=False`, so any instance loaded before is stale.

    NOTE for anyone adding a test here: `expire_all` also DISCARDS un-flushed
    pending changes on loaded objects. Never call this between a mutation and
    its commit -- use a `Query.update()` for setup writes instead, as the tests
    below do.
    """
    db.expire_all()
    return db.query(model).filter(model.id == row_id).first()


# ---------------------------------------------------------------------------
# the migration, pinned
# ---------------------------------------------------------------------------
def _load_migration(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load_migration("_rev_a1c4e8b60d37", MIGRATION_PATH)


@pytest.fixture(scope="module")
def eligibility_migration():
    return _load_migration("_rev_d3f8b2a70c19", ELIGIBILITY_MIGRATION_PATH)


def test_revision_chains_onto_the_expected_head(migration):
    assert migration.revision == "a1c4e8b60d37"
    assert migration.down_revision == "c9f2a7d81b45"


def test_the_eligibility_revision_chains_onto_the_archive_revision(eligibility_migration):
    assert eligibility_migration.revision == "d3f8b2a70c19"
    assert eligibility_migration.down_revision == "a1c4e8b60d37"
    assert eligibility_migration.ARCHIVABLE_TABLES == ("student_eligibilities",)


def test_every_archivable_model_is_in_the_migration(migration, eligibility_migration):
    """The two lists that must not drift: the ORM's and the migrations'."""
    from app.services.archive import ENTITY_MODELS

    from_models = {model.__tablename__ for model in ENTITY_MODELS.values()}
    from_migrations = set(migration.ARCHIVABLE_TABLES) | set(
        eligibility_migration.ARCHIVABLE_TABLES
    )
    assert from_models == from_migrations
    # No table gets the pair twice: two revisions both adding `archived_at` to
    # the same table is a failed upgrade, not a redundancy.
    assert not set(migration.ARCHIVABLE_TABLES) & set(
        eligibility_migration.ARCHIVABLE_TABLES
    )


def test_the_eligibility_migration_only_adds(eligibility_migration):
    """The non-destructive guard in scripts/db_migrate.py, asserted here too.

    That guard is what lets the operator run this revision against dev and prod
    without a human reading the diff first, so "upgrade() only adds" is a
    property of the file rather than a claim in its docstring.
    """
    import re
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        import db_migrate
    finally:
        sys.path.pop(0)

    body = db_migrate._upgrade_body(ELIGIBILITY_MIGRATION_PATH)
    assert body, "the guard could not find an upgrade() to read"
    hits = [p for p in db_migrate.DESTRUCTIVE_PATTERNS if re.search(p, body, re.IGNORECASE)]
    assert hits == [], hits


def test_the_backfill_timestamp_is_fixed_not_now(migration):
    """A legacy archive must not read as something that happened on deploy day."""
    assert migration.BACKFILL_TIMESTAMP == datetime(2000, 1, 1, 0, 0, 0)


def test_create_all_gives_every_archivable_table_the_pair():
    import app.models  # noqa: F401
    from app.db.base import Base
    from app.services.archive import ENTITY_MODELS

    assert "archive_events" in Base.metadata.tables
    for model in ENTITY_MODELS.values():
        columns = Base.metadata.tables[model.__tablename__].c
        assert "archived_at" in columns, model.__tablename__
        assert "archive_event_id" in columns, model.__tablename__
        assert columns["archived_at"].nullable is True
        assert columns["archive_event_id"].nullable is True


# ---------------------------------------------------------------------------
# cascade
# ---------------------------------------------------------------------------
def test_archiving_a_student_stamps_the_whole_graph_with_one_event(db, user, tree):
    from app.models.appointment import Appointment
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.student import Student
    from app.models.student_eligibility import StudentEligibility
    from app.models.therapy_session import TherapySession
    from app.services import archive as archive_service

    event = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"], reason="Moved away"
    )

    expected = [
        (Student, [tree["student"]]),
        (IEPGoal, [tree["goal_one"], tree["goal_two"]]),
        (GoalObjective, tree["objectives_of_goal_one"] + tree["objectives_of_goal_two"]),
        (ObjectiveProgressEntry, tree["entries_of_goal_one"] + tree["entries_of_goal_two"]),
        (TherapySession, [tree["session"]]),
        (Appointment, [tree["appointment"]]),
        (StudentEligibility, tree["eligibilities"]),
    ]
    for model, ids in expected:
        for row_id in ids:
            row = _row(db, model, row_id)
            assert row is not None, f"{model.__name__} {row_id} was DELETED, not archived"
            assert row.archived_at is not None, f"{model.__name__} {row_id} not stamped"
            assert row.archive_event_id == event.id, (
                f"{model.__name__} {row_id} carries event {row.archive_event_id}, "
                f"not {event.id} -- one archive must be one event"
            )

    assert event.root_entity_type == "student"
    assert event.root_entity_id == tree["student"]
    assert event.reason == "Moved away"
    assert event.restored_at is None

    counts = archive_service.event_contents(db, event.id)
    assert counts == {
        "students": 1,
        "goals": 2,
        "objectives": 4,
        "progressEntries": 4,
        "therapySessions": 1,
        "appointments": 1,
        "studentEligibilities": 2,
    }


def test_the_legacy_boolean_moves_with_the_timestamp(db, user, tree):
    """`students.is_archived` is still in the REST payload; it must never lag."""
    from app.models.student import Student
    from app.services import archive as archive_service

    event = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )
    row = _row(db, Student, tree["student"])
    assert row.archived_at is not None
    assert row.is_archived is True
    # The COLUMN, not the hybrid -- the two have to agree in the database, not
    # only in Python.
    raw = db.query(Student._is_archived).filter(Student.id == tree["student"]).scalar()
    assert raw is True

    archive_service.restore(db, user_id=user, event_id=event.id)
    row = _row(db, Student, tree["student"])
    assert row.archived_at is None
    assert row.is_archived is False
    raw = db.query(Student._is_archived).filter(Student.id == tree["student"]).scalar()
    assert raw is False


def test_a_pre_archived_goal_keeps_its_older_event(db, user, tree):
    """THE RULE. A student cascade must not re-stamp what was archived before."""
    from app.models.iep_goal import IEPGoal
    from app.services import archive as archive_service

    september = archive_service.archive(
        db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
    )
    january = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )
    assert september.id != january.id

    goal_one = _row(db, IEPGoal, tree["goal_one"])
    goal_two = _row(db, IEPGoal, tree["goal_two"])
    assert goal_one.archive_event_id == september.id, (
        "the student cascade re-stamped a goal that was already archived -- "
        "restoring the student would now resurrect it"
    )
    assert goal_two.archive_event_id == january.id

    # ...and the objectives and entries under the pre-archived goal went with
    # September, not January.
    from app.models.goal_objective import GoalObjective
    from app.models.objective_progress_entry import ObjectiveProgressEntry

    for objective_id in tree["objectives_of_goal_one"]:
        assert _row(db, GoalObjective, objective_id).archive_event_id == september.id
    for entry_id in tree["entries_of_goal_one"]:
        assert _row(db, ObjectiveProgressEntry, entry_id).archive_event_id == september.id


def test_cascade_shapes_are_what_the_deletes_they_replaced_destroyed(db, user, tree):
    from app.services import archive as archive_service

    goal = archive_service.preview(db, "goal", tree["goal_one"])
    assert goal == {"goals": 1, "objectives": 2, "progressEntries": 2}

    objective = archive_service.preview(
        db, "objective", tree["objectives_of_goal_one"][0]
    )
    assert objective == {"objectives": 1, "progressEntries": 1}

    entry = archive_service.preview(db, "progress_entry", tree["entries_of_goal_one"][0])
    assert entry == {"progressEntries": 1}

    # A therapy session takes NOTHING with it: its progress entries belong to an
    # objective and stay active. A deliberate divergence from the old delete.
    session = archive_service.preview(db, "therapy_session", tree["session"])
    assert session == {"therapySessions": 1}


def test_archiving_a_session_leaves_its_progress_entries_active(db, user, tree):
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.services import archive as archive_service

    entry_id = tree["entries_of_goal_one"][0]
    db.query(ObjectiveProgressEntry).filter(
        ObjectiveProgressEntry.id == entry_id
    ).update({"therapy_session_id": tree["session"]}, synchronize_session=False)
    db.commit()

    archive_service.archive(
        db, user_id=user, entity_type="therapy_session", entity_id=tree["session"]
    )
    assert _row(db, ObjectiveProgressEntry, entry_id).archived_at is None


def test_archiving_an_appointment_takes_its_therapy_session(db, user, tree):
    from app.models.therapy_session import TherapySession
    from app.services import archive as archive_service

    db.query(TherapySession).filter(TherapySession.id == tree["session"]).update(
        {"appointment_id": tree["appointment"]}, synchronize_session=False
    )
    db.commit()

    event = archive_service.archive(
        db, user_id=user, entity_type="appointment", entity_id=tree["appointment"]
    )
    assert _row(db, TherapySession, tree["session"]).archive_event_id == event.id


def test_archiving_a_time_block_takes_its_appointments_and_sessions(db, user, tree):
    from app.models.appointment import Appointment
    from app.models.block_assignment import BlockAssignment
    from app.models.therapy_session import TherapySession
    from app.models.time_block import TimeBlock
    from app.services import archive as archive_service

    block = TimeBlock(
        start_datetime=datetime(2026, 6, 10, 13, 0, 0),
        end_datetime=datetime(2026, 6, 10, 13, 45, 0),
        block_type="group_therapy",
        title="Group",
        status="active",
    )
    db.add(block)
    db.flush()
    # `Query.update` rather than attribute writes: `_row` expires the session,
    # and an expire between a pending change and its commit throws the change
    # away. See the note on `_row`.
    db.query(Appointment).filter(Appointment.id == tree["appointment"]).update(
        {"time_block_id": block.id}, synchronize_session=False
    )
    db.query(TherapySession).filter(TherapySession.id == tree["session"]).update(
        {"time_block_id": block.id}, synchronize_session=False
    )
    assignment = BlockAssignment(
        time_block_id=block.id, student_id=tree["student"], status="assigned"
    )
    db.add(assignment)
    db.commit()

    event = archive_service.archive(
        db, user_id=user, entity_type="time_block", entity_id=block.id
    )
    assert _row(db, TimeBlock, block.id).archive_event_id == event.id
    assert _row(db, Appointment, tree["appointment"]).archive_event_id == event.id
    assert _row(db, TherapySession, tree["session"]).archive_event_id == event.id

    # The join row is untouched: it carries no clinical content, has no archive
    # columns, and keeping it is what lets the restore hand the group back whole.
    surviving = _row(db, BlockAssignment, assignment.id)
    assert surviving is not None
    assert surviving.status == "assigned"


def test_double_archive_is_a_clear_error_not_a_silent_no_op(db, user, tree):
    """A no-op would hand back an event id that stamped nothing.

    Restoring THAT would appear to succeed and change nothing at all, which is
    the worst available failure: it looks like it worked.
    """
    from app.services import archive as archive_service

    first = archive_service.archive(
        db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
    )
    with pytest.raises(archive_service.AlreadyArchivedError) as raised:
        archive_service.archive(
            db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
        )
    assert raised.value.event_id == first.id
    assert str(first.id) in str(raised.value)

    # And no orphan event row was created by the refusal.
    events = archive_service.list_events(db, user_id=user, root_entity_type="goal")
    assert [e.id for e in events if e.root_entity_id == tree["goal_one"]] == [first.id]


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------
def test_restore_is_exact_and_the_older_event_stays_archived(db, user, tree):
    """Restore faithfulness, which is the whole reason events exist."""
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student
    from app.services import archive as archive_service

    september = archive_service.archive(
        db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
    )
    january = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )

    summary = archive_service.restore(db, user_id=user, event_id=january.id)

    assert _row(db, Student, tree["student"]).archived_at is None
    assert _row(db, IEPGoal, tree["goal_two"]).archived_at is None
    # The September goal STAYS archived, under its own event.
    goal_one = _row(db, IEPGoal, tree["goal_one"])
    assert goal_one.archived_at is not None
    assert goal_one.archive_event_id == september.id

    assert summary["restored"] == {
        "students": 1,
        "goals": 1,
        "objectives": 2,
        "progressEntries": 2,
        "therapySessions": 1,
        "appointments": 1,
        "studentEligibilities": 2,
    }
    assert summary["totalRows"] == 10

    event = archive_service.get_event(db, january.id)
    assert event.restored_at is not None
    assert event.restored_by_user_id == user


def test_restoring_a_child_under_an_archived_parent_is_blocked(db, user, tree):
    """No orphan resurrection: a live goal under a hidden student is unreachable."""
    from app.models.iep_goal import IEPGoal
    from app.services import archive as archive_service

    goal_event = archive_service.archive(
        db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
    )
    student_event = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )

    with pytest.raises(archive_service.ParentStillArchivedError) as raised:
        archive_service.restore(db, user_id=user, event_id=goal_event.id)

    message = str(raised.value)
    assert str(student_event.id) in message, message
    assert "student" in message, message
    assert raised.value.parent_event_id == student_event.id
    # Nothing moved.
    assert _row(db, IEPGoal, tree["goal_one"]).archived_at is not None
    assert archive_service.get_event(db, goal_event.id).restored_at is None

    # Restore the parent first, and then the child goes back.
    archive_service.restore(db, user_id=user, event_id=student_event.id)
    archive_service.restore(db, user_id=user, event_id=goal_event.id)
    assert _row(db, IEPGoal, tree["goal_one"]).archived_at is None


def test_restoring_twice_is_refused(db, user, tree):
    from app.services import archive as archive_service

    event = archive_service.archive(
        db, user_id=user, entity_type="goal", entity_id=tree["goal_one"]
    )
    archive_service.restore(db, user_id=user, event_id=event.id)
    with pytest.raises(archive_service.AlreadyRestoredError):
        archive_service.restore(db, user_id=user, event_id=event.id)


def test_an_archived_session_does_not_block_restoring_its_progress_entry(db, user, tree):
    """A session is a REFERENCE, not a parent -- `therapy_session_id` is nullable.

    The entry belongs to an objective. Blocking on the session would make an
    archived session quietly un-restorable data.
    """
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.services import archive as archive_service

    entry_id = tree["entries_of_goal_one"][0]
    db.query(ObjectiveProgressEntry).filter(
        ObjectiveProgressEntry.id == entry_id
    ).update({"therapy_session_id": tree["session"]}, synchronize_session=False)
    db.commit()

    entry_event = archive_service.archive(
        db, user_id=user, entity_type="progress_entry", entity_id=entry_id
    )
    archive_service.archive(
        db, user_id=user, entity_type="therapy_session", entity_id=tree["session"]
    )

    archive_service.restore(db, user_id=user, event_id=entry_event.id)
    assert _row(db, ObjectiveProgressEntry, entry_id).archived_at is None


# ---------------------------------------------------------------------------
# eligibility: the eighth archivable table
# ---------------------------------------------------------------------------
def test_an_eligibility_archives_as_a_leaf(db, user, tree):
    """Itself and nothing else -- and emphatically not its CATEGORY.

    `eligibility_categories` is the shared vocabulary the whole caseload points
    at. Sweeping one into a cascade would retire a disability category for every
    other child on the roster, which is the kind of blast radius this framework
    exists to prevent.
    """
    from app.models.eligibility_category import EligibilityCategory
    from app.models.student_eligibility import StudentEligibility
    from app.services import archive as archive_service

    first, second = tree["eligibilities"]
    category_id = _row(db, StudentEligibility, first).eligibility_category_id

    assert archive_service.preview(db, "student_eligibility", first) == {
        "studentEligibilities": 1
    }

    event = archive_service.archive(
        db,
        user_id=user,
        entity_type="student_eligibility",
        entity_id=first,
        reason="Determination superseded",
    )

    row = _row(db, StudentEligibility, first)
    assert row is not None, "the eligibility was DELETED, not archived"
    assert row.archived_at is not None
    assert row.archive_event_id == event.id
    # Every column it had, still there. An archived determination is a record,
    # not a tombstone.
    assert row.start_date is not None
    assert row.notes == "Qualifies under this category"

    assert _row(db, StudentEligibility, second).archived_at is None
    category = db.query(EligibilityCategory).filter(
        EligibilityCategory.id == category_id
    ).first()
    assert category is not None
    assert not hasattr(category, "archived_at"), (
        "eligibility_categories must NOT be archivable -- it is a shared lookup"
    )

    assert archive_service.event_contents(db, event.id) == {"studentEligibilities": 1}
    assert archive_service.root_student_id(db, "student_eligibility", first) == tree["student"]


def test_an_eligibility_round_trips_through_restore(db, user, tree):
    from app.models.student_eligibility import StudentEligibility
    from app.services import archive as archive_service

    first = tree["eligibilities"][0]
    before = _row(db, StudentEligibility, first)
    snapshot = (before.student_id, before.eligibility_category_id, before.start_date,
                before.is_primary, before.notes)

    event = archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=first
    )
    summary = archive_service.restore(db, user_id=user, event_id=event.id)
    assert summary["restored"] == {"studentEligibilities": 1}

    after = _row(db, StudentEligibility, first)
    assert after.archived_at is None
    assert after.archive_event_id is None
    assert (after.student_id, after.eligibility_category_id, after.start_date,
            after.is_primary, after.notes) == snapshot


def test_a_pre_archived_eligibility_keeps_its_older_event(db, user, tree):
    """THE RULE, on the newest table: a student cascade does not re-stamp."""
    from app.models.student_eligibility import StudentEligibility
    from app.services import archive as archive_service

    first, second = tree["eligibilities"]
    september = archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=first
    )
    january = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )

    assert _row(db, StudentEligibility, first).archive_event_id == september.id
    assert _row(db, StudentEligibility, second).archive_event_id == january.id

    archive_service.restore(db, user_id=user, event_id=january.id)
    assert _row(db, StudentEligibility, second).archived_at is None
    # The September determination stays archived, under its own event.
    assert _row(db, StudentEligibility, first).archived_at is not None
    assert _row(db, StudentEligibility, first).archive_event_id == september.id


def test_restoring_an_eligibility_under_an_archived_student_is_blocked(db, user, tree):
    from app.models.student_eligibility import StudentEligibility
    from app.services import archive as archive_service

    first = tree["eligibilities"][0]
    eligibility_event = archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=first
    )
    student_event = archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )

    with pytest.raises(archive_service.ParentStillArchivedError) as raised:
        archive_service.restore(db, user_id=user, event_id=eligibility_event.id)
    assert str(student_event.id) in str(raised.value)
    assert _row(db, StudentEligibility, first).archived_at is not None


def test_archiving_an_eligibility_twice_is_refused(db, user, tree):
    from app.services import archive as archive_service

    first = tree["eligibilities"][0]
    event = archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=first
    )
    with pytest.raises(archive_service.AlreadyArchivedError) as raised:
        archive_service.archive(
            db, user_id=user, entity_type="student_eligibility", entity_id=first
        )
    assert raised.value.event_id == event.id


def test_archive_many_is_one_event_for_a_whole_series(db, user, tree):
    from app.models.appointment import Appointment
    from app.services import archive as archive_service

    extra = Appointment(
        student_id=tree["student"],
        start_datetime=datetime(2026, 6, 17, 9, 0, 0),
        end_datetime=datetime(2026, 6, 17, 9, 30, 0),
        appointment_type="individual",
        status="scheduled",
    )
    db.add(extra)
    db.commit()

    event = archive_service.archive_many(
        db,
        user_id=user,
        entity_type="appointment",
        entity_ids=[tree["appointment"], extra.id],
        reason="series",
    )
    assert _row(db, Appointment, tree["appointment"]).archive_event_id == event.id
    assert _row(db, Appointment, extra.id).archive_event_id == event.id

    archive_service.restore(db, user_id=user, event_id=event.id)
    assert _row(db, Appointment, tree["appointment"]).archived_at is None
    assert _row(db, Appointment, extra.id).archived_at is None


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------
def test_delete_endpoints_archive_rather_than_delete(client, db, tree):
    """The compatibility contract: same routes, same verbs, rows survive."""
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.student import Student
    from app.models.student_eligibility import StudentEligibility
    from app.models.therapy_session import TherapySession

    cases = [
        (f"/api/goals/{tree['goal_one']}", IEPGoal, tree["goal_one"]),
        (
            f"/api/progress-entries/{tree['entries_of_goal_two'][0]}",
            ObjectiveProgressEntry,
            tree["entries_of_goal_two"][0],
        ),
        (
            f"/api/therapy-sessions/{tree['session']}",
            TherapySession,
            tree["session"],
        ),
        (
            f"/api/eligibilities/students/{tree['eligibilities'][0]}",
            StudentEligibility,
            tree["eligibilities"][0],
        ),
        (f"/api/students/{tree['student']}", Student, tree["student"]),
    ]
    for url, model, row_id in cases:
        response = client.delete(url)
        assert response.status_code == 200, (url, response.text)
        body = response.json()
        assert body["archived"] is True, url
        assert isinstance(body["archiveEventId"], int), url
        # The old message the React app already reads, unchanged.
        assert "deleted successfully" in body["message"], url

        row = _row(db, model, row_id)
        assert row is not None, f"{url} DELETED the row"
        assert row.archived_at is not None
        assert row.archive_event_id == body["archiveEventId"]


def test_the_archive_router_lists_and_restores(client, db, tree):
    from app.models.student import Student

    deleted = client.delete(f"/api/students/{tree['student']}")
    event_id = deleted.json()["archiveEventId"]

    events = client.get("/api/archive/events")
    assert events.status_code == 200
    listed = {row["eventId"]: row for row in events.json()}
    assert event_id in listed
    assert listed[event_id]["rootEntityType"] == "student"
    assert listed[event_id]["restored"] is False
    assert listed[event_id]["contents"]["goals"] == 2

    archived = client.get("/api/archive/archived/student")
    assert tree["student"] in {row["id"] for row in archived.json()}

    restored = client.post(f"/api/archive/events/{event_id}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"]["students"] == 1
    assert _row(db, Student, tree["student"]).archived_at is None

    # Twice is a 409, not a second success.
    assert client.post(f"/api/archive/events/{event_id}/restore").status_code == 409


def test_the_rest_archive_endpoints_still_speak_the_old_student_shape(client, db, tree):
    """`PUT /archive` and `PUT /unarchive` are what the React app calls."""
    archived = client.put(f"/api/students/{tree['student']}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True

    # ...and it really cascaded, which the old implementation never did.
    goals = client.get("/api/goals", params={"student_id": tree["student"]})
    assert goals.json() == []

    unarchived = client.put(f"/api/students/{tree['student']}/unarchive")
    assert unarchived.status_code == 200, unarchived.text
    assert unarchived.json()["is_archived"] is False
    goals = client.get("/api/goals", params={"student_id": tree["student"]})
    assert len(goals.json()) == 2


def test_an_archived_student_is_still_readable_by_id(client, tree):
    """The detail page is where the Unarchive button lives."""
    client.delete(f"/api/students/{tree['student']}")
    response = client.get(f"/api/students/{tree['student']}")
    assert response.status_code == 200
    assert response.json()["is_archived"] is True


def test_archiving_twice_over_rest_is_a_409(client, tree):
    assert client.delete(f"/api/students/{tree['student']}").status_code == 200
    assert client.delete(f"/api/students/{tree['student']}").status_code == 409


def test_the_eligibility_delete_route_archives_and_the_list_hides_it(client, db, tree):
    """The route that was still hard-deleting, end to end."""
    from app.models.student_eligibility import StudentEligibility

    first, second = tree["eligibilities"]
    student_id = tree["student"]

    listed = client.get(f"/api/eligibilities/students/{student_id}")
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {first, second}

    deleted = client.delete(
        f"/api/eligibilities/students/{first}",
        params={"reason": "Determination superseded"},
    )
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["archived"] is True
    assert isinstance(body["archiveEventId"], int)
    # The old message the React app already reads, unchanged.
    assert "deleted successfully" in body["message"]

    row = _row(db, StudentEligibility, first)
    assert row is not None, "the DELETE route destroyed the row"
    assert row.archive_event_id == body["archiveEventId"]

    listed = client.get(f"/api/eligibilities/students/{student_id}")
    assert {r["id"] for r in listed.json()} == {second}

    with_archived = client.get(
        f"/api/eligibilities/students/{student_id}",
        params={"include_archived": True},
    )
    assert {r["id"] for r in with_archived.json()} == {first, second}

    # It is in the archive ledger under its own entity type...
    archived = client.get("/api/archive/archived/student_eligibility")
    assert archived.status_code == 200, archived.text
    assert first in {r["id"] for r in archived.json()}

    # ...and restoring the event brings it back to the list.
    restored = client.post(f"/api/archive/events/{body['archiveEventId']}/restore")
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored"] == {"studentEligibilities": 1}
    listed = client.get(f"/api/eligibilities/students/{student_id}")
    assert {r["id"] for r in listed.json()} == {first, second}


def test_archiving_an_eligibility_twice_over_rest_is_a_409(client, tree):
    url = f"/api/eligibilities/students/{tree['eligibilities'][0]}"
    assert client.delete(url).status_code == 200
    assert client.delete(url).status_code == 409


def test_an_archived_eligibility_is_a_404_to_update(client, tree):
    """An archived id answers the way a deleted one used to."""
    first = tree["eligibilities"][0]
    assert client.delete(f"/api/eligibilities/students/{first}").status_code == 200
    response = client.put(
        f"/api/eligibilities/students/{first}", json={"notes": "reopened"}
    )
    assert response.status_code == 404, response.text


def test_the_student_payload_drops_an_archived_eligibility(client, tree):
    """The eager load, over the wire. `GET /api/students/{id}` nests them."""
    first, second = tree["eligibilities"]
    student = client.get(f"/api/students/{tree['student']}")
    assert {e["id"] for e in student.json()["eligibilities"]} == {first, second}

    client.delete(f"/api/eligibilities/students/{first}")
    student = client.get(f"/api/students/{tree['student']}")
    assert {e["id"] for e in student.json()["eligibilities"]} == {second}


# ---------------------------------------------------------------------------
# blind import
# ---------------------------------------------------------------------------
def test_uic_dedupe_still_catches_an_archived_student(db, user, tree):
    """A returning child is not a new one.

    `students.uic` is UNIQUE, so a validator blind to the archive would report
    "no such UIC" and then fail on the constraint. Worse, it would invite the
    therapist to create a second record beside the archived one.
    """
    import json

    from app.models.student import Student
    from app.services import archive as archive_service
    from app.mcp.privacy import build_contexts
    from app.services import blind_import

    alias = _row(db, Student, tree["student"]).student_alias
    db.query(Student).filter(Student.id == tree["student"]).update(
        {"uic": "UICARCHIVED001"}, synchronize_session=False
    )
    db.commit()
    archive_service.archive(
        db, user_id=user, entity_type="student", entity_id=tree["student"]
    )

    batch, _secret = blind_import.create_batch(db, user)
    blind_import.store_rows(
        db,
        batch,
        [
            {
                "name": "Caseload",
                "rows": [
                    (1, ["Student", "State ID"]),
                    (2, ["Restorio, Archie", "UICARCHIVED001"]),
                ],
            }
        ],
    )
    blind_import.set_mapping(
        db,
        batch,
        {
            "sheet": "Caseload",
            "header_row": 1,
            "data_start_row": 2,
            "columns": {"A": "full_name_last_first", "B": "uic"},
        },
        # The alias roster the reveal is scrubbed against, built the way the MCP
        # tool builds it.
        build_contexts(db, None),
    )
    report = blind_import.validate(db, batch)

    blob = json.dumps(report, default=str)
    assert "duplicate_uic_existing" in blob, blob
    # The alias, never the name -- and the fact that it is ARCHIVED, which is
    # the difference between "fix your spreadsheet" and "restore the record".
    assert alias in blob, blob
    assert "Archie" not in blob and "Restorio" not in blob, blob
    assert '"existingStudentArchived": true' in blob, blob


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------
@pytest.fixture
def as_principal(db, user, tree):
    from app.mcp import auth as mcp_auth
    from app.mcp.auth import McpPrincipal

    principal = McpPrincipal(
        user_id=user,
        token_id=1,
        user_name="Archive Tester",
        role="therapist",
        is_admin=False,
        access_mode="enforce",
        enforce_access=True,
        allowed_student_ids=[tree["student"]],
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


def test_the_delete_tools_are_gone():
    names = set(_tools())
    assert "delete_goal" not in names
    assert "delete_progress_entry" not in names
    assert {
        "archive_student",
        "archive_goal",
        "archive_objective",
        "archive_progress_entry",
        "archive_therapy_session",
        "restore_archived",
        "list_archive_events",
    } <= names


def test_mcp_archive_refuses_without_confirm_and_says_what_it_would_hide(
    db, as_principal, tree
):
    from app.models.iep_goal import IEPGoal

    tools = _tools()
    result = as_principal(tools["archive_goal"].fn, goal_id=tree["goal_one"])
    assert result["archived"] is False
    assert "confirm must be true" in result["reason"]
    assert result["wouldArchive"]["willArchive"] == {
        "goals": 1,
        "objectives": 2,
        "progressEntries": 2,
    }
    # Nothing happened.
    assert _row(db, IEPGoal, tree["goal_one"]).archived_at is None


def test_mcp_round_trips_a_student_through_archive_and_restore(db, as_principal, tree):
    from app.models.iep_goal import IEPGoal
    from app.models.student import Student

    tools = _tools()
    archived = as_principal(
        tools["archive_student"].fn,
        student_id=tree["student"],
        confirm=True,
        reason="left the district",
    )
    assert archived["archived"] is True
    event_id = archived["archiveEventId"]
    assert archived["contents"]["goals"] == 2
    assert _row(db, Student, tree["student"]).archived_at is not None

    events = as_principal(tools["list_archive_events"].fn)
    listed = {row["eventId"]: row for row in events}
    assert event_id in listed
    # Masked: the student is an ALIAS, never a name.
    assert listed[event_id]["student"] == f"student_{tree['student']}"

    restored = as_principal(
        tools["restore_archived"].fn, event_id=event_id, confirm=True
    )
    assert restored["restored"]["students"] == 1
    assert _row(db, Student, tree["student"]).archived_at is None
    assert _row(db, IEPGoal, tree["goal_one"]).archived_at is None


def test_mcp_restore_refuses_without_confirm(db, as_principal, tree):
    from app.models.student import Student

    tools = _tools()
    archived = as_principal(
        tools["archive_student"].fn, student_id=tree["student"], confirm=True
    )
    result = as_principal(
        tools["restore_archived"].fn, event_id=archived["archiveEventId"]
    )
    assert result["restored"] is False
    assert "confirm must be true" in result["reason"]
    assert _row(db, Student, tree["student"]).archived_at is not None


def test_mcp_reads_hide_archived_records(db, as_principal, tree):
    tools = _tools()
    as_principal(tools["archive_goal"].fn, goal_id=tree["goal_one"], confirm=True)

    goals = as_principal(tools["list_goals"].fn, student_id=tree["student"])
    assert tree["goal_one"] not in {g["id"] for g in goals}
    assert tree["goal_two"] in {g["id"] for g in goals}

    # And an archived id is "no such goal", not a back door.
    with pytest.raises(ValueError, match="No goal with id"):
        as_principal(tools["get_goal"].fn, goal_id=tree["goal_one"])


def test_mcp_get_student_omits_an_archived_eligibility(db, user, as_principal, tree):
    """The nested read an agent gets, filtered -- with the PII rules intact.

    `get_student` is the one tool that returns a student's eligibilities, and it
    returns them nested inside the student rather than as their own list, so the
    query filter alone would not have caught this: the eager load needs its own
    criteria. What an agent must never be handed is a determination somebody
    archived, quoted as current.
    """
    import json

    from app.models.student import Student
    from app.services import archive as archive_service

    first, second = tree["eligibilities"]
    tools = _tools()

    before = as_principal(tools["get_student"].fn, student_id=tree["student"])
    assert {e["id"] for e in before["eligibilities"]} == {first, second}

    archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=first
    )

    after = as_principal(tools["get_student"].fn, student_id=tree["student"])
    assert {e["id"] for e in after["eligibilities"]} == {second}

    # The PII contract, unchanged by any of the above: alias, never a name.
    student = _row(db, Student, tree["student"])
    blob = json.dumps(after, default=str)
    assert student.first not in blob, blob
    assert student.last not in blob, blob
    assert after["alias"] == f"student_{tree['student']}"
    assert "uic" not in blob and "date_of_birth" not in blob, blob


def test_mcp_list_archive_events_accepts_the_new_root_type(db, user, as_principal, tree):
    from app.services import archive as archive_service

    event = archive_service.archive(
        db, user_id=user, entity_type="student_eligibility", entity_id=tree["eligibilities"][0]
    )
    tools = _tools()
    events = as_principal(
        tools["list_archive_events"].fn, root_entity_type="student_eligibility"
    )
    listed = {row["eventId"]: row for row in events}
    assert event.id in listed
    assert listed[event.id]["rootEntityType"] == "student_eligibility"
    # Masked: the student is an ALIAS, never a name.
    assert listed[event.id]["student"] == f"student_{tree['student']}"


def test_mcp_archive_outputs_carry_no_student_name(db, as_principal, tree):
    """The choke point still holds over the new tools."""
    import json

    from app.models.student import Student

    student = _row(db, Student, tree["student"])
    tools = _tools()
    blobs = [
        json.dumps(
            as_principal(tools["archive_student"].fn, student_id=tree["student"]),
            default=str,
        ),
        json.dumps(
            as_principal(tools["archive_goal"].fn, goal_id=tree["goal_one"]), default=str
        ),
    ]
    for blob in blobs:
        assert student.first not in blob, blob
        assert student.last not in blob, blob
