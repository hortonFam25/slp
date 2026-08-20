"""The PII gate on /mcp.

This module exists to fail. Specifically, it is written so that the three ways
this protection realistically rots each turn CI red:

1. **Someone registers a tool with the raw `@mcp_server.tool()`.** The registry
   walk in `test_every_registered_tool_is_pii_filtered` enumerates the LIVE
   FastMCP registry — not a list maintained here — and demands the
   `__pii_filtered__` marker that only `app.mcp.server.tool` applies.

2. **Someone adds a tool and nobody ever exercises it.** `ARG_FACTORY` below is
   checked against that same live registry, so a new tool with no entry fails
   before it has a chance to leak quietly.

3. **Someone widens a payload.** Every tool in the registry is actually CALLED
   against a seeded database whose students carry deliberately unmistakable
   PII, and the FULL serialized JSON of every result is searched for it. A new
   field that happens to carry a name, a DOB or a UIC is caught by the search
   rather than by a reviewer.

The sentinels ("Zebulonqx", "Vandergriff", "UICSENTINEL123", …) are nonsense on
purpose: any occurrence anywhere in a response is a leak and cannot be a
coincidence, so the assertions need no allow-list and no fuzzy matching.

Two students are seeded — one on the test principal's caseload and one
deliberately off it — and the off-caseload student's name is composed into the
ON-caseload student's notes, which is the leak an access check cannot catch and
only free-text redaction can.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import pytest

# ---------------------------------------------------------------------------
# sentinels
# ---------------------------------------------------------------------------
S1_FIRST = "Zebulonqx"
S1_LAST = "Vandergriff"
S1_UIC = "UICSENTINEL123"
S1_DOB = date(2011, 3, 17)

S2_FIRST = "Quixotellez"
S2_LAST = "Marchetti"
S2_UIC = "UICSENTINEL456"
S2_DOB = date(2009, 7, 23)

# Every string that must never appear in anything /mcp emits.
SENTINELS = (
    S1_FIRST,
    S1_LAST,
    f"{S1_FIRST} {S1_LAST}",
    S1_UIC,
    S1_DOB.isoformat(),
    S2_FIRST,
    S2_LAST,
    f"{S2_FIRST} {S2_LAST}",
    S2_UIC,
    S2_DOB.isoformat(),
)

# Field names that must not survive anywhere in a payload, at any depth, in any
# casing or separator style. Compared on a normalised key, so `date_of_birth`,
# `dateOfBirth` and `DateOfBirth` are all the same entry.
DENYLISTED_KEYS = frozenset({"first", "last", "uic", "dateofbirth", "dob", "birthdate"})

_NORMALIZE = re.compile(r"[^a-z0-9]+")


def _normalize_key(key: str) -> str:
    return _NORMALIZE.sub("", str(key).lower())


def _walk_keys(value, path="$"):
    """Every (normalised key, json path) pair in a nested structure."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield _normalize_key(key), f"{path}.{key}"
            yield from _walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_keys(item, f"{path}[{index}]")


def assert_clean(label: str, value) -> None:
    """The whole assertion, applied to one tool's output."""
    blob = json.dumps(value, default=str)
    lowered = blob.lower()
    for sentinel in SENTINELS:
        assert sentinel.lower() not in lowered, (
            f"{label} leaked the sentinel {sentinel!r}:\n{blob[:2000]}"
        )
    for normalized, path in _walk_keys(value):
        assert normalized not in DENYLISTED_KEYS, (
            f"{label} emitted a denylisted key at {path}:\n{blob[:2000]}"
        )


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def seed(client):
    """Two students with sentinel PII, and a record tree hanging off the first.

    Depends on ``client`` only for its side effect: the app's startup handler is
    what runs ``create_all`` against the throwaway sqlite file.
    """
    from app.db.database import SessionLocal
    from app.models.appointment import Appointment
    from app.models.goal_category import GoalCategory
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.school import School
    from app.models.student import Student
    from app.models.teacher import Teacher
    from app.models.therapy_session import TherapySession

    db = SessionLocal()
    try:
        school = School(name="Northgate Elementary", district="Northgate ISD")
        teacher = Teacher(first_name="Marla", last_name="Pennington", title="Teacher")
        category = GoalCategory(name="Articulation (pii-test)")
        db.add_all([school, teacher, category])
        db.flush()

        one = Student(
            student_alias="pending-1",
            first=S1_FIRST,
            last=S1_LAST,
            uic=S1_UIC,
            date_of_birth=S1_DOB,
            grade_level="3",
            enrollment_status="Active",
            school_id=school.id,
            teacher_id=teacher.id,
            case_manager_id=teacher.id,
            iep_date=date(2026, 1, 5),
            annual_review_due_date=date(2026, 12, 4),
        )
        two = Student(
            student_alias="pending-2",
            first=S2_FIRST,
            last=S2_LAST,
            uic=S2_UIC,
            date_of_birth=S2_DOB,
            grade_level="5",
            enrollment_status="Active",
            school_id=school.id,
        )
        db.add_all([one, two])
        db.flush()
        # Match the app's own alias convention now that the ids exist.
        one.student_alias = f"student_{one.id}"
        two.student_alias = f"student_{two.id}"
        db.flush()

        # Names composed into clinical prose — the leak that field-stripping
        # alone cannot reach. Note that student TWO is named inside student
        # ONE's record: the caller may read this note and may NOT read that
        # student.
        goal = IEPGoal(
            student_id=one.id,
            goal_category_id=category.id,
            goal_number="1",
            goal_description=(
                f"{S1_FIRST} {S1_LAST} will produce /r/ in conversation with 80% "
                f"accuracy, including during paired drills with {S2_FIRST} "
                f"{S2_LAST}."
            ),
            target_criteria=f"80% across 3 sessions for {S1_FIRST}",
            baseline_data=f"{S1_LAST} scored 20% at baseline",
            goal_status="Active",
            start_date=date(2026, 1, 5),
        )
        db.add(goal)
        db.flush()

        objective = GoalObjective(
            goal_id=goal.id,
            objective_number=1,
            objective_description=(
                f"Given a model, {S1_FIRST} will produce initial /r/ in 8 of 10 trials."
            ),
            progress_status="In Progress",
            schedule_frequency="weekly",
        )
        second_objective = GoalObjective(
            goal_id=goal.id,
            objective_number=2,
            objective_description=f"{S1_LAST} will self-correct /r/ errors.",
        )
        db.add_all([objective, second_objective])
        db.flush()

        entry = ObjectiveProgressEntry(
            objective_id=objective.id,
            progress_date=date(2026, 2, 10),
            progress_on_objective="8/10 trials",
            progress_comments=(
                f"{S1_FIRST} {S1_LAST} was engaged; {S2_FIRST} {S2_LAST} modelled "
                f"the target sound."
            ),
            therapist_initials="AH",
            session_type="individual",
        )
        db.add(entry)

        session_row = TherapySession(
            student_id=one.id,
            session_date=datetime(2026, 2, 10, 10, 0, 0),
            start_time=datetime(2026, 2, 10, 10, 0, 0),
            end_time=datetime(2026, 2, 10, 10, 30, 0),
            planned_duration_minutes=30,
            session_type="individual",
            status="planned",
            created_from="manual",
            prep_notes=f"Warm-up cards chosen for {S1_FIRST}.",
            session_notes=f"{S1_FIRST} {S1_LAST} produced /r/ in 8 of 10 trials.",
        )
        db.add(session_row)

        tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        appointment = Appointment(
            student_id=one.id,
            teacher_id=teacher.id,
            school_id=school.id,
            start_datetime=tomorrow.replace(hour=9),
            end_datetime=tomorrow.replace(hour=9, minute=30),
            appointment_type="individual",
            status="scheduled",
            location="Room 4",
            notes=f"Pick {S1_FIRST} {S1_LAST} up from {teacher.last_name}'s room.",
        )
        db.add(appointment)
        db.commit()

        return {
            "student_one": one.id,
            "student_two": two.id,
            "alias_one": f"student_{one.id}",
            "school": school.id,
            "teacher": teacher.id,
            "category": category.id,
            "goal": goal.id,
            "objective": objective.id,
            "objective_two": second_objective.id,
            "entry": entry.id,
            "session": session_row.id,
            "appointment": appointment.id,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def principal(seed):
    """A NON-admin therapist who may see student one and not student two.

    `access_mode="enforce"` on purpose: 'monitor' (what the rest of the suite
    runs in) lets every student through, which would make the off-caseload half
    of these assertions vacuous.
    """
    from app.mcp.auth import McpPrincipal

    return McpPrincipal(
        user_id=4242,
        token_id=1,
        user_name="Pytest Therapist",
        role="therapist",
        is_admin=False,
        access_mode="enforce",
        enforce_access=True,
        allowed_student_ids=[seed["student_one"]],
    )


@pytest.fixture
def as_principal(principal):
    """Run a callable inside the contextvar the middleware would have set."""
    from app.mcp import auth as mcp_auth

    def run(fn, /, **kwargs):
        token = mcp_auth._CURRENT.set(principal)
        try:
            return fn(**kwargs)
        finally:
            mcp_auth._CURRENT.reset(token)

    return run


# ---------------------------------------------------------------------------
# ARG_FACTORY — one entry per registered tool
# ---------------------------------------------------------------------------
# `seed` -> the keyword arguments to call that tool with. Adding a tool without
# adding an entry here fails `test_every_registered_tool_has_an_arg_factory`.
# Write tools really write (the sqlite file is a scratch DB); the two
# destructive tools are exercised with confirm=False, which is the branch that
# returns a `wouldDelete` summary — a payload that is itself worth searching
# for PII.
ARG_FACTORY = {
    "get_caseload_overview": lambda s: {},
    "list_students": lambda s: {"include_archived": True},
    "get_student": lambda s: {"student_id": s["student_one"]},
    "list_goals": lambda s: {"student_id": s["student_one"]},
    "get_goal": lambda s: {"goal_id": s["goal"]},
    "list_objectives": lambda s: {"goal_id": s["goal"]},
    "list_progress_entries": lambda s: {"objective_id": s["objective"]},
    "list_therapy_sessions": lambda s: {"student_id": s["student_one"]},
    "get_therapy_session": lambda s: {"session_id": s["session"]},
    "get_schedule": lambda s: {
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=6)).isoformat(),
    },
    "list_schools": lambda s: {},
    "list_teachers": lambda s: {},
    "list_eligibility_categories": lambda s: {},
    "list_goal_categories": lambda s: {},
    "create_progress_entry": lambda s: {
        "objective_id": s["objective"],
        "progress_date": "2026-03-02",
        "progress_on_objective": "9/10 trials",
        "progress_comments": f"{S1_FIRST} {S1_LAST} generalised to conversation.",
        "therapist_initials": "AH",
    },
    "update_progress_entry": lambda s: {
        "entry_id": s["entry"],
        "progress_comments": (
            f"Revised: {S1_FIRST} needed two prompts while {S2_FIRST} {S2_LAST} watched."
        ),
    },
    "create_goal": lambda s: {
        "student_id": s["student_one"],
        "goal_category_id": s["category"],
        "goal_description": f"{S1_FIRST} {S1_LAST} will use /s/ blends in sentences.",
        "target_criteria": "80% across 3 sessions",
        "start_date": "2026-01-05",
    },
    "update_goal": lambda s: {
        "goal_id": s["goal"],
        "baseline_data": f"{S1_LAST} scored 25% on re-baseline",
    },
    "create_objective": lambda s: {
        "goal_id": s["goal"],
        "objective_number": 7,
        "objective_description": f"{S1_FIRST} will produce /r/ in phrases.",
    },
    "update_objective": lambda s: {
        "objective_id": s["objective_two"],
        "objective_description": f"{S1_FIRST} {S1_LAST} will self-correct /r/ errors.",
    },
    "create_therapy_session": lambda s: {
        "student_id": s["student_one"],
        "session_date": "2026-03-09T10:00:00",
        "prep_notes": f"Cards picked out for {S1_FIRST}.",
        "planned_goal_ids": [s["goal"]],
        "planned_objective_ids": [s["objective"]],
    },
    "complete_therapy_session": lambda s: {
        "session_id": s["session"],
        "session_notes": f"{S1_FIRST} {S1_LAST} worked hard.",
        "student_engagement": "high",
        "goals_addressed": True,
    },
    "update_student": lambda s: {"student_id": s["student_one"], "grade_level": "4"},
    "delete_progress_entry": lambda s: {"entry_id": s["entry"], "confirm": False},
    "delete_goal": lambda s: {"goal_id": s["goal"], "confirm": False},
}


# ---------------------------------------------------------------------------
# structural enforcement
# ---------------------------------------------------------------------------
def test_registry_is_not_empty():
    """A registry that failed to populate would make every other test vacuous."""
    from app.mcp.server import registered_tools

    assert len(registered_tools()) >= 25


def test_every_registered_tool_is_pii_filtered():
    """The drift gate: a tool added with the raw decorator fails here."""
    from app.mcp.server import registered_tools

    unfiltered = [
        tool.name
        for tool in registered_tools()
        if not getattr(tool.fn, "__pii_filtered__", False)
    ]
    assert not unfiltered, (
        "These MCP tools are not behind the PII filter. Register them with "
        "`@tool()` from app.mcp.server, not `@mcp_server.tool()`: "
        f"{sorted(unfiltered)}"
    )


def test_every_registered_tool_has_an_arg_factory():
    """A new tool must be exercised by this suite, not merely marked."""
    from app.mcp.server import registered_tools

    registered = {tool.name for tool in registered_tools()}
    missing = registered - set(ARG_FACTORY)
    stale = set(ARG_FACTORY) - registered
    assert not missing, f"No ARG_FACTORY entry for: {sorted(missing)}"
    assert not stale, f"ARG_FACTORY entries for tools that no longer exist: {sorted(stale)}"


def test_wrapping_preserves_the_tool_schema():
    """The filter must be invisible to a client: same params, same description."""
    from app.mcp.server import registered_tools

    by_name = {tool.name: tool for tool in registered_tools()}
    assert sorted(by_name["get_student"].parameters["properties"]) == ["student_id"]
    assert by_name["get_student"].description


# ---------------------------------------------------------------------------
# every tool, every result
# ---------------------------------------------------------------------------
def test_no_tool_leaks_student_pii(seed, as_principal):
    """Call all 25 tools for real and search the whole JSON of every result."""
    from app.mcp.server import registered_tools

    called = []
    for tool in registered_tools():
        args = ARG_FACTORY[tool.name](seed)
        result = as_principal(tool.fn, **args)
        assert_clean(f"tool {tool.name}", result)
        called.append(tool.name)

    assert len(called) == len(ARG_FACTORY)


def test_free_text_names_become_aliases(seed, as_principal):
    """Not merely absent — replaced, so the note still reads as a sentence."""
    from app.mcp.server import registered_tools

    by_name = {tool.name: tool for tool in registered_tools()}
    # `get_goal` rather than a progress entry: the goal description names both
    # students and no write tool in ARG_FACTORY rewrites it, so this holds
    # whatever order the tests run in.
    goal = as_principal(by_name["get_goal"].fn, goal_id=seed["goal"])
    blob = json.dumps(goal, default=str)
    assert seed["alias_one"] in blob, blob
    # The off-caseload student named inside an accessible note is aliased too.
    assert f"student_{seed['student_two']}" in blob, blob


def test_alias_is_the_display_identity(seed, as_principal):
    """Utility check: stripping names must not leave an unusable payload."""
    from app.mcp.server import registered_tools

    by_name = {tool.name: tool for tool in registered_tools()}

    student = as_principal(by_name["get_student"].fn, student_id=seed["student_one"])
    assert student["id"] == seed["student_one"]
    assert student["alias"] == seed["alias_one"]
    assert student["displayName"] == seed["alias_one"]
    # The clinical fields the server exists to serve are still there.
    assert student["grade_level"]
    assert student["enrollment_status"] == "Active"
    assert student["iep_date"] == "2026-01-05"
    assert student["school"]["name"] == "Northgate Elementary"

    rows = as_principal(by_name["list_students"].fn, include_archived=True)
    assert rows, "the caseload should not be empty"
    mine = [row for row in rows if row["id"] == seed["student_one"]]
    assert mine and mine[0]["alias"] == seed["alias_one"]


def test_staff_names_are_kept_in_v1(seed, as_principal):
    """The documented v1 policy, asserted so flipping it is a deliberate act.

    Teacher and school names are organisational context, not student PII. If
    `REDACT_STAFF_NAMES` is turned on, this test is the one that tells you the
    policy changed rather than something breaking by accident.
    """
    from app.mcp.privacy import REDACT_STAFF_NAMES
    from app.mcp.server import registered_tools

    if REDACT_STAFF_NAMES:
        pytest.skip("staff-name redaction is on; this asserts the v1 default")

    by_name = {tool.name: tool for tool in registered_tools()}
    teachers = as_principal(by_name["list_teachers"].fn)
    blob = json.dumps(teachers, default=str)
    assert "Pennington" in blob, blob


# ---------------------------------------------------------------------------
# error paths
# ---------------------------------------------------------------------------
def test_error_message_does_not_echo_a_name_back(seed, as_principal):
    """A parser that echoes its input is an exfiltration oracle if unfiltered.

    `progress_date` is interpolated verbatim into the ValueError, so passing a
    student's name as the date is the cheapest way to ask the server to say it.
    """
    from app.mcp.server import registered_tools

    by_name = {tool.name: tool for tool in registered_tools()}
    with pytest.raises(ValueError) as raised:
        as_principal(
            by_name["create_progress_entry"].fn,
            objective_id=seed["objective"],
            progress_date=f"{S1_FIRST} {S1_LAST}",
        )
    message = str(raised.value)
    assert_clean("create_progress_entry error", message)
    assert seed["alias_one"] in message, message


def test_access_denied_error_is_clean(seed, as_principal):
    """The off-caseload student's identity must not surface in the refusal."""
    from app.mcp.server import registered_tools

    by_name = {tool.name: tool for tool in registered_tools()}
    with pytest.raises(ValueError) as raised:
        as_principal(by_name["get_student"].fn, student_id=seed["student_two"])
    assert_clean("get_student denied", str(raised.value))


def test_sanitized_error_rewrites_a_composed_name(seed, as_principal):
    """The wrapper's error path, exercised directly on a composed message."""
    from app.mcp import server as mcp_module

    def build():
        contexts = mcp_module._alias_contexts()
        return mcp_module._sanitized_error(
            ValueError(f"Student {S1_FIRST} {S1_LAST} not found"), contexts
        )

    rebuilt = as_principal(build)
    assert isinstance(rebuilt, ValueError)
    assert_clean("sanitized error", str(rebuilt))
    assert str(rebuilt) == f"Student {seed['alias_one']} not found"


# ---------------------------------------------------------------------------
# the sanitizer itself
# ---------------------------------------------------------------------------
def test_sanitizer_is_recursive_and_deterministic():
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import sanitize_tool_result

    contexts = [
        StudentAliasContext(
            student_id=7, alias="student_7", first_name="Zebulonqx", last_name="Vandergriff"
        )
    ]
    payload = {
        "studentId": 7,
        "first": "Zebulonqx",
        "last": "Vandergriff",
        "uic": "UICSENTINEL123",
        "dateOfBirth": "2011-03-17",
        "notes": ["Zebulonqx did well", {"deep": "spoke with Vandergriff today"}],
        "gradeLevel": "3",
    }
    once = sanitize_tool_result(payload, contexts)
    twice = sanitize_tool_result(once, contexts)

    assert once == twice, "sanitizing twice must be a no-op"
    assert "uic" not in once and "dateOfBirth" not in once
    assert once["first"] == "student_7" and once["last"] == "student_7"
    assert once["notes"][0] == "student_7 did well"
    assert once["notes"][1]["deep"] == "spoke with student_7 today"
    assert once["gradeLevel"] == "3"
    assert once["studentId"] == 7


def test_unattributable_name_field_is_dropped_not_kept():
    """No alias to substitute means the field goes, not that it survives."""
    from app.mcp.privacy import sanitize_tool_result

    out = sanitize_tool_result({"student": "Someone Unknown", "kind": "note"}, [])
    assert "student" not in out
    assert out["kind"] == "note"


def test_short_names_do_not_shred_text():
    """A one-character name must not turn every matching letter into an alias."""
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import sanitize_tool_result

    contexts = [StudentAliasContext(student_id=9, alias="student_9", first_name="A", last_name="")]
    out = sanitize_tool_result({"note": "A steady session, good carryover."}, contexts)
    assert out["note"] == "A steady session, good carryover."
