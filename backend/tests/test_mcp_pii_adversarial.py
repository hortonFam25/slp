"""The PII gate on /mcp, attacked rather than demonstrated.

`test_mcp_pii.py` is the drift suite: it walks the registry, calls every tool
and proves the filter is wired to all of them. This file is its adversary. Each
test here started as a way of getting a child's identity out through /mcp that
WORKED against the first version of `app.mcp.privacy`, and every one of them is
now the regression test for the fix.

The attacks fall into four families:

1. **Identifiers written into prose.** The structural layer removes the
   `date_of_birth` and `uic` COLUMNS. It has nothing to say about a clinician
   who typed "DOB 3/17/2011, UIC 4471...", into a progress comment, which is
   where those two identifiers actually live in a caseload that has been in use
   for a year.

2. **Names the roster could not recognise.** The scrubber matches the name as
   the database spells it. A note does not: it drops the accent off "José",
   composes the same accent differently after a copy-paste, or writes half of
   "Garcia-Lopez".

3. **Shapes the recursion walked past.** The sanitizer understood dicts, lists
   and strings, and returned everything else untouched — so a tool that forgot
   to `_dump` its Pydantic response model, or returned a dataclass or a set,
   was unfiltered by construction and no drift test could see it.

4. **Errors raised where the tool decorator cannot reach.** FastMCP validates
   arguments before the tool body runs; that failure is the SDK's, not the
   tool's, and it quotes the offending value back.

Alongside those, the two things a redaction layer must NOT do — corrupt a
compliance date that happens to collide with a birthday, and shred ordinary
prose — are asserted here too, because a filter that fails those gets turned
off by whoever is on call, and a filter that is off protects nobody.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta

import pytest

# ---------------------------------------------------------------------------
# sentinels — distinct from test_mcp_pii.py's, so a failure names its own file
# ---------------------------------------------------------------------------
A_FIRST = "José"                     # accented, NFC in the database
A_LAST = "Quillingsworth-Braddock"   # compound: a note will write half of it
A_UIC = "UICADVERSARY7788"
A_DOB = date(2011, 3, 17)

# The unaccented and decomposed spellings of A_FIRST. Neither is the string in
# the database and both identify the same child.
A_FIRST_FOLDED = "Jose"
A_FIRST_DECOMPOSED = "José"
A_LAST_HALF = "Quillingsworth"

# A second student, off the caseload, whose DOB is deliberately the SAME as a
# date the first student's record legitimately carries — see
# test_a_compliance_date_is_not_corrupted_by_a_colliding_birthday.
B_FIRST = "Ondraxis"
B_LAST = "Fenwicke"
B_UIC = "UICADVERSARY9911"
# Relative to today on purpose: it has to fall inside get_caseload_overview's
# 60-day annual-review window to exercise that branch, and that window moves.
B_DOB = date.today() + timedelta(days=30)

TEACHER_EMAIL = "m.pennington-adversary@northgate.example"

# Every rendering of A_DOB that a note might use and that must not survive.
DOB_SPELLINGS = (
    "2011-03-17",
    "3/17/2011",
    "03/17/2011",
    "17/03/2011",
    "03-17-2011",
    "03/17/11",
    "March 17, 2011",
    "Mar 17 2011",
    "17 March 2011",
)


def _blob(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def hostile(client):
    """A caseload written the way a real one is: identifiers loose in prose.

    Depends on ``client`` only for its side effect — the app's startup handler
    is what creates the schema in the throwaway sqlite file.
    """
    from app.db.database import SessionLocal
    from app.models.appointment import Appointment
    from app.models.block_assignment import BlockAssignment
    from app.models.goal_category import GoalCategory
    from app.models.goal_objective import GoalObjective
    from app.models.iep_goal import IEPGoal
    from app.models.objective_progress_entry import ObjectiveProgressEntry
    from app.models.school import School
    from app.models.student import Student
    from app.models.teacher import Teacher
    from app.models.time_block import TimeBlock

    db = SessionLocal()
    try:
        school = School(name="Westbrook Adversary Elementary", district="Westbrook ISD")
        teacher = Teacher(
            first_name="Marla",
            last_name="Pennington",
            title="Teacher",
            email=TEACHER_EMAIL,
        )
        category = GoalCategory(name="Articulation (adversarial)")
        db.add_all([school, teacher, category])
        db.flush()

        one = Student(
            student_alias="adv-pending-1",
            first=A_FIRST,
            last=A_LAST,
            uic=A_UIC,
            date_of_birth=A_DOB,
            grade_level="3",
            enrollment_status="Active",
            school_id=school.id,
            teacher_id=teacher.id,
            case_manager_id=teacher.id,
            iep_date=date(2026, 1, 5),
            # Inside the 60-day window, so get_caseload_overview's
            # annualReviewsDueWithin60Days branch is actually exercised, and
            # equal to student two's DOB, so the collision case is live.
            annual_review_due_date=B_DOB,
        )
        two = Student(
            student_alias="adv-pending-2",
            first=B_FIRST,
            last=B_LAST,
            uic=B_UIC,
            date_of_birth=B_DOB,
            grade_level="5",
            enrollment_status="Active",
            school_id=school.id,
        )
        db.add_all([one, two])
        db.flush()
        one.student_alias = f"student_{one.id}"
        two.student_alias = f"student_{two.id}"
        db.flush()

        goal = IEPGoal(
            student_id=one.id,
            goal_category_id=category.id,
            goal_number="1",
            goal_description=(
                f"Per the file: DOB {A_DOB.isoformat()} (also written "
                f"3/17/2011 and March 17, 2011), UIC {A_UIC}. "
                f"{A_FIRST_FOLDED} will produce /r/ in conversation."
            ),
            target_criteria="80% across 3 sessions",
            baseline_data=f"{A_LAST_HALF} scored 20% at baseline",
            goal_status="Active",
            start_date=date(2026, 1, 5),
        )
        db.add(goal)
        db.flush()

        objective = GoalObjective(
            goal_id=goal.id,
            objective_number=1,
            objective_description=(
                f"Given a model, {A_FIRST_DECOMPOSED} will produce initial /r/ "
                f"in 8 of 10 trials."
            ),
            progress_status="In Progress",
            schedule_frequency="weekly",
        )
        db.add(objective)
        db.flush()

        entry = ObjectiveProgressEntry(
            objective_id=objective.id,
            progress_date=date(2026, 2, 10),
            progress_on_objective="8/10 trials",
            progress_comments=(
                f"Verified identity against the SIS: {A_UIC}, born 03/17/2011. "
                f"{A_FIRST_FOLDED} {A_LAST_HALF} was engaged throughout."
            ),
            therapist_initials="AH",
            session_type="individual",
        )
        db.add(entry)

        tomorrow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
        block = TimeBlock(
            title="Group /r/ block",
            block_type="group",
            start_datetime=tomorrow.replace(hour=11),
            end_datetime=tomorrow.replace(hour=11, minute=30),
            status="scheduled",
            location="Room 7",
            teacher_id=teacher.id,
            school_id=school.id,
        )
        db.add(block)
        db.flush()
        # Both students on the block: the roster path has to filter the
        # off-caseload one out AND alias the one it keeps.
        db.add_all(
            [
                BlockAssignment(time_block_id=block.id, student_id=one.id, status="assigned"),
                BlockAssignment(time_block_id=block.id, student_id=two.id, status="assigned"),
            ]
        )

        appointment = Appointment(
            student_id=one.id,
            teacher_id=teacher.id,
            school_id=school.id,
            time_block_id=block.id,
            start_datetime=tomorrow.replace(hour=9),
            end_datetime=tomorrow.replace(hour=9, minute=30),
            appointment_type="individual",
            status="scheduled",
            location="Room 4",
            notes=f"Collect {A_FIRST_FOLDED} (UIC {A_UIC}) from room 12.",
        )
        db.add(appointment)
        db.commit()

        return {
            "student_one": one.id,
            "student_two": two.id,
            "alias_one": f"student_{one.id}",
            "alias_two": f"student_{two.id}",
            "school": school.id,
            "teacher": teacher.id,
            "category": category.id,
            "goal": goal.id,
            "objective": objective.id,
            "entry": entry.id,
            "block": block.id,
            "appointment": appointment.id,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def principal(hostile):
    """A non-admin therapist who may see student one and not student two."""
    from app.mcp.auth import McpPrincipal

    return McpPrincipal(
        user_id=4243,
        token_id=2,
        user_name="Pytest Adversary",
        role="therapist",
        is_admin=False,
        access_mode="enforce",
        enforce_access=True,
        allowed_student_ids=[hostile["student_one"]],
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


@pytest.fixture
def tools():
    from app.mcp.server import registered_tools

    return {tool.name: tool for tool in registered_tools()}


# ---------------------------------------------------------------------------
# 1. identifiers written into prose
# ---------------------------------------------------------------------------
def test_a_date_of_birth_in_free_text_does_not_survive(hostile, as_principal, tools):
    """The leak: the DOB COLUMN is stripped, the DOB in the note was not.

    Three spellings in one goal description, because a filter that catches ISO
    and misses "3/17/2011" has caught the format the app writes and missed the
    format a human writes.
    """
    goal = as_principal(tools["get_goal"].fn, goal_id=hostile["goal"])
    blob = _blob(goal)
    for spelling in ("2011-03-17", "3/17/2011", "March 17, 2011"):
        assert spelling not in blob, f"DOB spelling {spelling!r} survived:\n{blob}"


def test_a_uic_in_free_text_does_not_survive(hostile, as_principal, tools):
    """Same leak, other identifier — and in a progress comment, not a goal."""
    entries = as_principal(
        tools["list_progress_entries"].fn, objective_id=hostile["objective"]
    )
    assert A_UIC not in _blob(entries), _blob(entries)


def test_every_dob_spelling_is_scrubbed_from_prose():
    """The format table itself, at the unit level rather than through a tool."""
    from app.mcp.privacy import McpStudentContext, scrub_text

    contexts = [
        McpStudentContext(
            student_id=7,
            alias="student_7",
            first_name="Unrelated",
            last_name="Person",
            date_of_birth=A_DOB,
            uic=A_UIC,
        )
    ]
    for spelling in DOB_SPELLINGS:
        out = scrub_text(f"Chart review: born {spelling} per the SIS.", contexts)
        assert spelling not in out, f"{spelling!r} survived: {out!r}"


def test_identifiers_become_a_marker_not_an_alias():
    """A DOB is not an identity, so it must not be rewritten to one.

    "born student_7" would read to a model as a second child in the room. The
    replacement has to say that something was removed, not name somebody.
    """
    from app.mcp.privacy import IDENTIFIER_PLACEHOLDER, McpStudentContext, scrub_text

    contexts = [
        McpStudentContext(
            student_id=7,
            alias="student_7",
            first_name="Unrelated",
            last_name="Person",
            date_of_birth=A_DOB,
            uic=A_UIC,
        )
    ]
    out = scrub_text(f"born {A_DOB.isoformat()}, uic {A_UIC}", contexts)
    assert out == f"born {IDENTIFIER_PLACEHOLDER}, uic {IDENTIFIER_PLACEHOLDER}"


def test_a_short_identifier_does_not_shred_text():
    """A two-character UIC is not scrubbed: it would eat every "10" in a note."""
    from app.mcp.privacy import McpStudentContext, scrub_text

    contexts = [
        McpStudentContext(
            student_id=8, alias="student_8", first_name="", last_name="", uic="10"
        )
    ]
    text = "10 of 10 trials correct."
    assert scrub_text(text, contexts) == text


def test_a_compliance_date_is_not_corrupted_by_a_colliding_birthday(
    hostile, as_principal, tools
):
    """The cost side of the DOB scrub, held to account.

    Student one's annual review falls on student two's birthday — a collision
    that is rare but not impossible on a real caseload. Every date this server
    emits is a string by the time it reaches the scrubber, so a naive DOB scrub
    would blank a legal deadline and nobody would ever see why. A value that is
    EXACTLY a date is a structured field and survives; the same date inside a
    sentence does not.
    """
    student = as_principal(tools["get_student"].fn, student_id=hostile["student_one"])
    assert student["annual_review_due_date"] == B_DOB.isoformat(), student

    overview = as_principal(tools["get_caseload_overview"].fn)
    due = overview["annualReviewsDueWithin60Days"]
    assert due, "the 60-day review branch must actually be exercised"
    assert due[0]["annualReviewDue"] == B_DOB.isoformat(), due


# ---------------------------------------------------------------------------
# 2. names the roster could not recognise
# ---------------------------------------------------------------------------
def test_an_accent_folded_name_is_still_redacted(hostile, as_principal, tools):
    """The database says "José"; the note says "Jose". Same child."""
    goal = as_principal(tools["get_goal"].fn, goal_id=hostile["goal"])
    blob = _blob(goal)
    assert A_FIRST_FOLDED not in blob, blob
    assert hostile["alias_one"] in blob, blob


def test_a_differently_composed_name_is_still_redacted(hostile, as_principal, tools):
    """NFC in the roster, NFD in the note — a copy-paste away from each other."""
    objectives = as_principal(tools["list_objectives"].fn, goal_id=hostile["goal"])
    blob = _blob(objectives)
    assert A_FIRST not in blob, blob
    assert A_FIRST_FOLDED not in blob, blob
    assert hostile["alias_one"] in blob, blob


def test_half_of_a_compound_surname_is_still_redacted(hostile, as_principal, tools):
    """"Quillingsworth-Braddock" in the file, "Quillingsworth" in the note."""
    goal = as_principal(tools["get_goal"].fn, goal_id=hostile["goal"])
    assert A_LAST_HALF not in _blob(goal), _blob(goal)


def test_a_short_compound_part_does_not_shred_text():
    """The cost side of splitting compounds: "Al-Sayed" must not eat every "Al"."""
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import scrub_text

    contexts = [
        StudentAliasContext(
            student_id=9, alias="student_9", first_name="Amy", last_name="Al-Sayed"
        )
    ]
    text = "Al the therapy dog visited; carryover was good."
    assert scrub_text(text, contexts) == text


def test_ordinary_prose_is_left_alone():
    """A scrub nobody can trust the output of is a scrub somebody turns off."""
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import scrub_text

    contexts = [
        StudentAliasContext(
            student_id=10, alias="student_10", first_name="Jose", last_name="Marchetti"
        )
    ]
    text = (
        "Produced /r/ in 8 of 10 trials with moderate verbal prompting; "
        "generalisation to conversation is emerging."
    )
    assert scrub_text(text, contexts) == text


# ---------------------------------------------------------------------------
# 3. shapes the recursion walked past
# ---------------------------------------------------------------------------
def test_an_undumped_pydantic_model_is_sanitized():
    """A tool that forgot `_dump` used to hand the response model straight out.

    The recursion understood dict/list/str and returned everything else as it
    came, so the one mistake most likely to be made — returning the schema
    object the REST route returns — was the one mistake with no filter on it.
    """
    from app.mcp.privacy import McpStudentContext, sanitize_tool_result
    from app.schemas.student import StudentSummary

    model = StudentSummary(
        id=11,
        student_alias="student_11",
        first=A_FIRST,
        last=A_LAST,
        uic=A_UIC,
        grade_level="3",
        enrollment_status="Active",
    )
    contexts = [
        McpStudentContext(
            student_id=11,
            alias="student_11",
            first_name=A_FIRST,
            last_name=A_LAST,
            uic=A_UIC,
        )
    ]
    out = sanitize_tool_result(model, contexts)
    blob = _blob(out)
    assert isinstance(out, dict)
    assert A_FIRST not in blob and A_LAST not in blob and A_UIC not in blob, blob
    assert out["grade_level"] == "3"


def test_a_dataclass_result_is_sanitized():
    import dataclasses

    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import sanitize_tool_result

    @dataclasses.dataclass
    class Row:
        student_id: int
        note: str

    contexts = [
        StudentAliasContext(
            student_id=12, alias="student_12", first_name=A_FIRST, last_name=A_LAST
        )
    ]
    out = sanitize_tool_result(Row(student_id=12, note=f"{A_FIRST} did well"), contexts)
    assert out == {"student_id": 12, "note": "student_12 did well"}


def test_a_set_result_is_sanitized():
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import sanitize_tool_result

    contexts = [
        StudentAliasContext(
            student_id=13, alias="student_13", first_name=A_FIRST, last_name=A_LAST
        )
    ]
    out = sanitize_tool_result({f"{A_FIRST} {A_LAST}", "unrelated"}, contexts)
    assert sorted(out) == ["student_13", "unrelated"]


# ---------------------------------------------------------------------------
# 4. errors the tool decorator cannot reach
# ---------------------------------------------------------------------------
def test_sdk_argument_validation_errors_are_filtered(hostile, principal):
    """FastMCP validates arguments BEFORE the tool body — outside `@tool()`.

    Its ValidationError quotes `input_value=...` back verbatim, on the same
    wire and in the same shape as a leak. This drives the real
    `FastMCP.call_tool`, which is the path a client's request actually takes.
    """
    from app.mcp import auth as mcp_auth
    from app.mcp.server import mcp_server

    async def go():
        try:
            await mcp_server.call_tool(
                "get_student", {"student_id": f"{A_FIRST} {A_LAST}"}
            )
        except Exception as exc:  # ToolError from the SDK
            return str(exc)
        return ""

    token = mcp_auth._CURRENT.set(principal)
    try:
        message = asyncio.run(go())
    finally:
        mcp_auth._CURRENT.reset(token)

    assert message, "the bad argument should have failed"
    assert A_FIRST not in message and A_LAST not in message, message
    assert hostile["alias_one"] in message, message


def test_the_sdk_error_filter_is_installed():
    """The marker, so removing the shim is a red test rather than a quiet gap."""
    from app.mcp.server import mcp_server

    assert getattr(mcp_server._tool_manager.call_tool, "__pii_filtered__", False)


def test_a_tool_body_error_is_still_filtered_through_the_real_call_path(
    hostile, principal
):
    """The `@tool()` path and the SDK path must not disagree about the answer."""
    from app.mcp import auth as mcp_auth
    from app.mcp.server import mcp_server

    async def go():
        try:
            await mcp_server.call_tool(
                "create_progress_entry",
                {"objective_id": hostile["objective"], "progress_date": A_UIC},
            )
        except Exception as exc:
            return str(exc)
        return ""

    token = mcp_auth._CURRENT.set(principal)
    try:
        message = asyncio.run(go())
    finally:
        mcp_auth._CURRENT.reset(token)

    assert message, "an unparseable date should have failed"
    assert A_UIC not in message, message


# ---------------------------------------------------------------------------
# surfaces the drift suite did not reach
# ---------------------------------------------------------------------------
def test_the_group_block_roster_is_aliased_and_scoped(hostile, as_principal, tools):
    """get_schedule's timeBlocks branch: only reachable with a seeded block.

    Two students are assigned to the block and one of them is off the caseload,
    so this asserts both halves at once — the roster is filtered AND what is
    left is an alias.
    """
    schedule = as_principal(
        tools["get_schedule"].fn,
        start_date=date.today().isoformat(),
        end_date=(date.today() + timedelta(days=6)).isoformat(),
    )
    blocks = [b for b in schedule["timeBlocks"] if b["timeBlockId"] == hostile["block"]]
    assert blocks, schedule
    roster = blocks[0]["students"]
    assert [row["student"] for row in roster] == [hostile["alias_one"]], roster
    assert hostile["alias_two"] not in _blob(schedule), _blob(schedule)


def test_no_tool_leaks_the_adversarial_sentinels(hostile, as_principal, tools):
    """Every read tool, against the hostile seed, searched for every spelling.

    The drift suite already calls every tool; this repeats the sweep against
    data written the way a used caseload is written — identifiers in prose,
    names in the spellings the roster does not hold.
    """
    from app.mcp.server import registered_tools

    forbidden = (
        A_FIRST,
        A_FIRST_FOLDED,
        A_FIRST_DECOMPOSED,
        A_LAST,
        A_LAST_HALF,
        A_UIC,
        B_FIRST,
        B_LAST,
        B_UIC,
        TEACHER_EMAIL,
        *DOB_SPELLINGS,
    )
    reads = {
        "get_caseload_overview": {},
        "list_students": {"include_archived": True},
        "get_student": {"student_id": hostile["student_one"]},
        "list_goals": {"student_id": hostile["student_one"]},
        "get_goal": {"goal_id": hostile["goal"]},
        "list_objectives": {"goal_id": hostile["goal"]},
        "list_progress_entries": {"objective_id": hostile["objective"]},
        "get_schedule": {
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=6)).isoformat(),
        },
        "list_teachers": {},
        "list_schools": {},
        # The archive family replaced delete_goal / delete_progress_entry.
        # confirm=False throughout: that branch composes a `wouldArchive`
        # summary out of the very fields this fixture poisoned -- goal text,
        # objective descriptions, progress comments -- and nothing is archived,
        # so the adversarial fixtures survive for the assertions below.
        "archive_goal": {"goal_id": hostile["goal"], "confirm": False},
        "archive_progress_entry": {"entry_id": hostile["entry"], "confirm": False},
        "archive_objective": {"objective_id": hostile["objective"], "confirm": False},
        "archive_student": {"student_id": hostile["student_one"], "confirm": False},
        "list_archive_events": {"include_restored": True},
    }
    assert set(reads) <= {tool.name for tool in registered_tools()}

    for name, args in reads.items():
        blob = _blob(as_principal(tools[name].fn, **args))
        for sentinel in forbidden:
            assert sentinel not in blob, f"{name} leaked {sentinel!r}:\n{blob[:2000]}"


def test_contact_details_are_not_served_over_mcp(hostile, as_principal, tools):
    """Staff NAMES are organisational context and stay. A mailbox is not.

    `TeacherSummary.email` rides along inside list_teachers and inside the
    nested teacher on every student summary. No tool here can send mail, so
    nothing downstream needs it, and a direct line to a child's teacher is not
    something to leave in a model vendor's transcript store.
    """
    teachers = as_principal(tools["list_teachers"].fn)
    blob = _blob(teachers)
    assert TEACHER_EMAIL not in blob, blob
    assert "Pennington" in blob, blob  # the v1 staff-name policy, unchanged

    students = as_principal(tools["list_students"].fn, include_archived=True)
    assert TEACHER_EMAIL not in _blob(students), _blob(students)


def test_the_tool_catalogue_itself_carries_no_pii(hostile):
    """tools/list is served before any tool runs, so nothing filters it.

    Descriptions and schemas are static text written by us — but they are the
    one part of the MCP surface the choke point never sees, so the sentinels
    are asserted against them explicitly rather than assumed.
    """
    from app.mcp.server import SERVER_INSTRUCTIONS, mcp_server

    catalogue = asyncio.run(mcp_server.list_tools())
    blob = _blob([tool.model_dump() for tool in catalogue]) + SERVER_INSTRUCTIONS
    for sentinel in (A_FIRST, A_LAST, A_UIC, B_FIRST, B_LAST, B_UIC, TEACHER_EMAIL):
        assert sentinel not in blob


# ---------------------------------------------------------------------------
# 5. the tokeniser's own edges
# ---------------------------------------------------------------------------
# Scrubbing word by word rather than by one giant alternation is what keeps the
# filter's cost proportional to the text instead of to the caseload — see
# `_Scrubber`. It also moves the failure mode: a leak is now a name the
# TOKENISER did not hand to the lookup, which is a quieter bug than a name the
# lookup did not contain. These pin the edges that actually bit.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A name in quotes. The closing quote must not be swallowed into the
        # token — this is exactly how a name survived an error message that
        # reads `(got 'Vandergriff')`.
        ("(got 'Fenwicke')", "(got 'student_X')"),
        # Possessive, the commonest shape a name takes in a note.
        ("Fenwicke's turn to lead", "student_X's turn to lead"),
        # A name glued into a hyphenated word.
        ("pre-Fenwicke baseline", "pre-student_X baseline"),
        # A full name is two tokens and must come back as ONE alias.
        ("Ondraxis Fenwicke was engaged", "student_X was engaged"),
        # Reversed, with punctuation between: two aliases is the honest answer.
        ("Fenwicke, Ondraxis", "student_X, student_X"),
        # Trailing punctuation of every kind.
        ("Seen by Fenwicke.", "Seen by student_X."),
        ("Fenwicke; then Ondraxis!", "student_X; then student_X!"),
        # Ordinary clinical prose is untouched.
        ("8 of 10 trials with moderate prompting", "8 of 10 trials with moderate prompting"),
    ],
)
def test_the_tokeniser_finds_names_wherever_punctuation_puts_them(text, expected):
    from app.ai.privacy import StudentAliasContext
    from app.mcp.privacy import scrub_text

    contexts = [
        StudentAliasContext(
            student_id=21, alias="student_21", first_name=B_FIRST, last_name=B_LAST
        )
    ]
    assert scrub_text(text, contexts) == expected.replace("student_X", "student_21")


def test_the_compiled_lookup_is_never_stale(hostile, as_principal, tools):
    """The scrubber's lookup is cached; the ROSTER it is built from is not.

    `build_contexts` reads every name from the database on every call, and the
    cache is keyed by what it read — so a student enrolled between two tool
    calls is redacted on the second one. A cache that survived a roster change
    would be a filter that does not know about the newest child in the
    building, which is the one case where being slightly stale is a breach.
    """
    from app.db.database import SessionLocal
    from app.models.student import Student

    latecomer_first = "Theloniusk"
    latecomer_last = "Ravenscroft"

    # Warm the cache on the roster as it stands.
    before = _blob(as_principal(tools["get_goal"].fn, goal_id=hostile["goal"]))
    assert latecomer_first not in before

    db = SessionLocal()
    try:
        newcomer = Student(
            student_alias="adv-pending-3",
            first=latecomer_first,
            last=latecomer_last,
            enrollment_status="Active",
        )
        db.add(newcomer)
        db.flush()
        newcomer.student_alias = f"student_{newcomer.id}"
        db.commit()
        newcomer_id = newcomer.id

        from app.models.iep_goal import IEPGoal

        row = db.query(IEPGoal).filter(IEPGoal.id == hostile["goal"]).first()
        original = row.goal_description
        row.goal_description = (
            f"{original} Paired with {latecomer_first} {latecomer_last}."
        )
        db.commit()
    finally:
        db.close()

    after = _blob(as_principal(tools["get_goal"].fn, goal_id=hostile["goal"]))
    assert latecomer_first not in after, after
    assert latecomer_last not in after, after
    assert f"student_{newcomer_id}" in after, after


# ---------------------------------------------------------------------------
# 6. the whole door, over HTTP
# ---------------------------------------------------------------------------
def test_the_real_http_endpoint_serves_no_pii(client, hostile):
    """Everything above drives the tools directly. This drives the DOOR.

    A real `slp_` key in the database, a real JSON-RPC POST to /mcp, through
    the auth middleware, the SDK's ASGI app, the tool and the filter — and the
    assertion is against the bytes on the wire, which is the only surface that
    actually reaches a client. If some layer between the tool's `return` and
    the response body reintroduced a name, nothing else in this suite would see
    it and this test would.
    """
    from app.db.database import SessionLocal
    from app.models.user import User
    from app.services import api_tokens as api_tokens_service

    db = SessionLocal()
    try:
        user = User(
            external_auth_id="pytest-adversary-mcp",
            email="adversary@example.invalid",
            display_name="Pytest Adversary",
            role="basic",
            is_active=True,
        )
        db.add(user)
        db.flush()
        _row, secret = api_tokens_service.create_token(db, user.id, "adversarial")
        db.commit()
    finally:
        db.close()

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    def rpc(method: str, params: dict | None = None) -> str:
        body = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        response = client.post("/mcp", json=body, headers=headers)
        assert response.status_code == 200, (response.status_code, response.text)
        return response.text

    # The catalogue, then the payload most likely to carry a name.
    wire = rpc("tools/list")
    wire += rpc(
        "tools/call",
        {"name": "get_goal", "arguments": {"goal_id": hostile["goal"]}},
    )
    wire += rpc(
        "tools/call",
        {"name": "get_student", "arguments": {"student_id": hostile["student_one"]}},
    )
    # An error, over the same wire: the SDK reports a failed tool call as a
    # RESULT with isError, not as a transport error, so the message is bytes on
    # this connection exactly like a payload is.
    wire += rpc(
        "tools/call",
        {
            "name": "create_progress_entry",
            "arguments": {
                "objective_id": hostile["objective"],
                "progress_date": f"{A_FIRST} {A_LAST}",
            },
        },
    )

    for sentinel in (
        A_FIRST,
        A_FIRST_FOLDED,
        A_LAST,
        A_LAST_HALF,
        A_UIC,
        B_FIRST,
        B_LAST,
        B_UIC,
        TEACHER_EMAIL,
        *DOB_SPELLINGS,
    ):
        assert sentinel not in wire, f"/mcp put {sentinel!r} on the wire:\n{wire[:3000]}"

    # Not merely absent: the alias is what a client actually receives.
    assert hostile["alias_one"] in wire, wire[:3000]


def test_the_real_http_endpoint_refuses_a_bad_key(client):
    """The filter is the second line. This is the first one, still standing."""
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert client.post("/mcp", json=body).status_code == 401
    assert (
        client.post(
            "/mcp", json=body, headers={"Authorization": "Bearer slp_not_a_real_key"}
        ).status_code
        == 401
    )
