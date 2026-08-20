"""
The SLP Pro MCP server — the machine door onto one therapist's caseload.

Shape of the thing:

  * FastMCP with stateless_http=True, json_response=True. No SSE, no session
    state: every call carries its own Authorization header and is answered on
    the spot, which is what lets the app keep running as a single Azure worker
    that may be recycled between two calls from the same agent.
  * Caseload scoping is NOT a parameter. It comes from the key (see
    app.mcp.auth), so there is no tool an agent can call that reaches a
    student the therapist cannot see, and no id it can guess that changes that.
  * Tools open their OWN session from the session factory. FastAPI's
    request-scoped `Depends(get_db)` never runs here — the SDK calls these
    functions directly.
  * Reads and writes go through the SAME repositories and the SAME Pydantic
    schemas the REST routes use, and repeat the same access checks the routers
    make. There is no MCP-only data path, so a rule added to the API is a rule
    the agent gets too, on the same deploy.

Descriptions are written for an agent that has never seen this app: what comes
back, what the ids mean, and which tool to pair it with.
"""

from __future__ import annotations

import functools
import logging
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session

from app.ai.privacy import StudentAliasContext
from app.db.database import SessionLocal
from app.mcp.auth import McpPrincipal, current_principal
from app.mcp.privacy import (
    build_contexts,
    sanitize_error_message,
    sanitize_tool_result,
)
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.models.student import Student
from app.models.therapy_session import TherapySession
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.eligibility_repository import EligibilityRepository
from app.repositories.goal_category_repository import GoalCategoryRepository
from app.repositories.goal_repository import (
    GoalRepository,
    ObjectiveRepository,
    ProgressEntryRepository,
)
from app.repositories.school_repository import SchoolRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.teacher_repository import TeacherRepository
from app.repositories.therapy_session_repository import TherapySessionRepository
from app.repositories.time_block_repository import TimeBlockRepository
from app.routers.therapy_sessions import (
    _build_session_response,
    _build_session_summary,
)
from app.schemas.eligibility import EligibilityCategoryRead
from app.schemas.goal_category import GoalCategoryRead
from app.schemas.goal_objective import (
    GoalObjectiveRead,
    GoalObjectiveUpdate,
    GoalObjectiveWithProgress,
    ObjectiveProgressEntryCreate,
    ObjectiveProgressEntryRead,
    ObjectiveProgressEntryUpdate,
)
from app.schemas.iep_goal import IEPGoalCreate, IEPGoalRead, IEPGoalUpdate, IEPGoalWithObjectives
from app.schemas.school import SchoolSummary
from app.schemas.student import StudentRead, StudentSummary, StudentUpdate
from app.schemas.teacher import TeacherSummary
from app.schemas.therapy_session import (
    CompleteSessionRequest,
    TherapySessionCreate,
    TherapySessionFilters,
)

logger = logging.getLogger(__name__)

SERVER_NAME = "slppro"

SERVER_INSTRUCTIONS = """\
SLP Pro is a speech-language pathologist's caseload manager: the students on
one therapist's caseload, their IEP goals, the objectives under each goal, the
progress entries logged against those objectives, the therapy sessions run with
them, and the weekly schedule of appointments and group time blocks.

Everything you can see through these tools belongs to the ONE therapist whose
connection key opened this session, and is filtered to the students that
therapist is allowed to see. There is no therapist parameter anywhere and no id
you can pass that reaches somebody else's caseload — a student outside it comes
back as "not found or not on your caseload", not as data.

STUDENTS ARE IDENTIFIED BY ALIAS, NEVER BY NAME. Every student appears as a
numeric id and an alias of the form "student_12", and that alias IS the
student's identity for the whole of this connection — use it when you refer to
a student, in summaries, in drafts, in anything you write back. Real names,
dates of birth and state identifiers (UIC) are not available over this
connection and never will be: they are removed from every result and every
error before it leaves the server, by design, not by omission. Do not ask for
them, do not try to infer them, and do not treat their absence as an error to
work around. If a human needs to see who student_12 is, they look it up in the
SLP Pro app, which is allowed to show them.

Every tool that takes a student takes the NUMERIC id (student_id=12), which is
the number in the alias and the `id` on every student row.

Start with get_caseload_overview. Ids returned by any list_* tool are the ids
the matching get_*, update_* and create_* tools expect, and the hierarchy is
always the same: student -> goal -> objective -> progress entry.

Reading is free. The write tools change a clinical record that a school's IEP
paperwork is built from, so say what you are about to write, and for whom,
before you write it. Exactly TWO tools destroy anything —
delete_progress_entry and delete_goal — and both refuse to run unless they are
told confirm=true; delete_goal takes every objective and every progress entry
under it with it.

Two vocabularies are worth fetching before you write: list_goal_categories
(every goal must name one) and list_eligibility_categories (the disability
categories a student qualifies under).

Dates are ISO-8601 strings: "2026-05-14" for a date, "2026-05-14T10:30:00" for
a time.
"""

# DNS-rebinding protection is the SDK's default when it thinks it is serving
# localhost, and its allow-list is localhost-only — which would answer 421 to
# every request in production, where the Host header is the Azure hostname.
# Turning it off is safe HERE and only here: the protection exists to stop a
# browser page from driving a local MCP server using AMBIENT credentials, and
# this endpoint has none — it accepts exactly one credential, an `slp_` bearer
# that no browser possesses and that CORS would never attach on its own.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)

mcp_server = FastMCP(
    SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
    stateless_http=True,
    json_response=True,
    transport_security=_TRANSPORT_SECURITY,
)


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------
def _session() -> Session:
    """
    A session of this call's own.

    Deliberately not `Depends(get_db)`: a tool body is invoked by the SDK, not
    by FastAPI's router, so there is no request to hang a dependency off.
    """
    return SessionLocal()


def _ctx() -> McpPrincipal:
    return current_principal()


# --------------------------------------------------------------------------
# the PII choke point
# --------------------------------------------------------------------------
def _alias_contexts() -> tuple[StudentAliasContext, ...]:
    """
    The roster the scrubber redacts against, in a session of its own.

    Same pattern as a tool body — its own short SessionLocal, closed
    immediately — so nothing about a tool's signature or its own session has to
    change to be filtered.
    """
    try:
        principal: Optional[McpPrincipal] = _ctx()
    except RuntimeError:  # pragma: no cover - the middleware makes this unreachable
        principal = None
    db = _session()
    try:
        return build_contexts(db, principal)
    finally:
        db.close()


def _sanitized_error(exc: BaseException, contexts) -> BaseException:
    """
    The same failure, with any student name scrubbed out of its message.

    Tools raise ValueError with composed text, and that text reaches the model
    verbatim (the SDK re-wraps it as `Error executing tool <name>: <message>`).
    Two ways a name gets in: the server composes one, or — the easier one to
    miss — the message echoes an argument the CALLER passed, which is how a
    date parser turns into an exfiltration oracle.
    """
    original = str(exc)
    cleaned = sanitize_error_message(original, contexts)
    if cleaned == original:
        return exc
    try:
        return type(exc)(cleaned)
    except Exception:  # pragma: no cover - exotic exception signatures
        return ValueError(cleaned)


def tool(*decorator_args, **decorator_kwargs) -> Callable:
    """
    Register an MCP tool. USE THIS, never `@mcp_server.tool()` directly.

    It does what the SDK's decorator does, and then the thing this server
    cannot leave to per-tool discipline: it wraps the function so that

      * its RETURN VALUE goes through `sanitize_tool_result`, and
      * any exception it raises has its MESSAGE sanitized before it is
        re-raised,

    against a roster rebuilt for this call. A tool author cannot forget the
    filter, cannot opt out of it, and cannot leak through an error path,
    because none of that is written in the tool.

    The wrapper carries `__pii_filtered__ = True`, and
    `backend/tests/test_mcp_pii.py` walks the live FastMCP registry asserting
    every registered tool has it — so a tool added with the raw decorator turns
    CI red instead of shipping.

    `functools.wraps` keeps the signature and the docstring, which is what
    FastMCP builds the tool's schema and description from, so the wrapping is
    invisible to a client.

    Failure is CLOSED: if the roster cannot be built (database down), the
    exception propagates and the unfiltered result is discarded rather than
    returned unscrubbed.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                # `from None`: the original message is the thing being
                # scrubbed, so it must not survive as a __cause__ that some
                # traceback formatter later prints.
                raise _sanitized_error(exc, _alias_contexts()) from None
            return sanitize_tool_result(result, _alias_contexts())

        wrapper.__pii_filtered__ = True
        mcp_server.tool(*decorator_args, **decorator_kwargs)(wrapper)
        return wrapper

    return decorator


def _install_sdk_error_filter() -> None:
    """
    The SECOND choke point: everything the SDK raises around a tool body.

    `tool()` above covers what a tool raises. It cannot cover what is raised
    BEFORE the tool is entered, because the SDK gets there first: FastMCP
    validates the arguments against a generated Pydantic model, and a failure
    there is a `ToolError` whose text quotes `input_value=...` verbatim. Today
    that value is the caller's own argument, so it is an echo rather than a
    leak — but the shape is exactly the shape of a leak, it lands on the same
    wire, and the next thing the SDK decides to interpolate into an error is
    not ours to choose.

    `FastMCP.call_tool` resolves `self._tool_manager.call_tool` at call time,
    so replacing that attribute puts a filter under everything the manager
    raises — argument validation, unknown tool, result conversion — without
    forking the SDK or re-registering a handler.

    Failure is CLOSED. If the roster cannot be built, the original message is
    discarded for a generic one rather than passed through unfiltered: an error
    nobody can read is a bad day, an error carrying a child's name is a breach.
    """
    manager = mcp_server._tool_manager
    inner = manager.call_tool
    if getattr(inner, "__pii_filtered__", False):  # pragma: no cover - import-once
        return

    @functools.wraps(inner)
    async def guarded(*args, **kwargs):
        try:
            return await inner(*args, **kwargs)
        except Exception as exc:
            try:
                contexts = _alias_contexts()
            except Exception:  # pragma: no cover - database down
                raise ValueError(
                    "The MCP server could not complete that call."
                ) from None
            raise _sanitized_error(exc, contexts) from None

    guarded.__pii_filtered__ = True
    manager.call_tool = guarded


def registered_tools() -> list:
    """
    Every tool in the live FastMCP registry, as SDK `Tool` objects.

    `Tool.fn` is the wrapper `tool()` produced, which is what lets the drift
    test check the `__pii_filtered__` marker. Reaching into `_tool_manager` is
    deliberate: the public `FastMCP.list_tools()` is async and returns the
    wire-protocol shape, which has the name and the schema but not the callable
    — and the callable is the thing under test.
    """
    return list(mcp_server._tool_manager.list_tools())


class _AuthShim:
    """
    Just enough of `AuthContext` for the response builders the REST routes use.

    Those builders (`_build_session_response`, `_build_session_summary`) ask an
    AuthContext exactly one question — whether student names should be shown as
    aliases — and reusing them rather than re-deriving thirty fields by hand is
    what keeps the agent's view of a session identical to the app's. Both
    compose a `student_name` field, which is precisely the field that must not
    carry a name here.

    So the answer to that one question is hard-coded to YES, for every caller,
    including the therapist who owns the caseload. The REST layer's rule
    ("admins and impersonators see aliases") does not apply on this side of the
    door: over MCP the reader is a model, never the therapist, so there is no
    owner exception to grant. `is_admin=True` is how the shim says "mask",
    not a claim of privilege — nothing else in those builders reads it.
    """

    __slots__ = ("is_admin", "user", "effective_user")

    class _User:
        __slots__ = ("id",)

        def __init__(self, user_id: int) -> None:
            self.id = user_id

    def __init__(self, principal: McpPrincipal) -> None:
        self.is_admin = True
        self.user = self._User(principal.user_id)
        self.effective_user = self.user


def _dump(model_cls, obj: Any) -> dict:
    """
    A row -> the SAME JSON the REST route would emit, minus nulls.

    Reusing the response schema rather than hand-rolling a dict is what keeps
    the agent's view and the app's view from drifting: a field added to the API
    appears here on the same deploy.
    """
    return model_cls.model_validate(obj).model_dump(exclude_none=True, mode="json")


def _dump_many(model_cls, rows: Any) -> list[dict]:
    return [_dump(model_cls, row) for row in rows]


def _scope_ids(ctx: McpPrincipal) -> Optional[list[int]]:
    """
    The `allowed_student_ids` argument the routers hand to the repositories.

    None means "no filter", and it is what the routers pass whenever the mode
    is not 'enforce' or the caller is an admin. Keeping the shape identical is
    the point: a repository that behaves one way for HTTP and another for MCP
    would be a second, untested access path.
    """
    if ctx.is_admin or not ctx.enforce_access:
        return None
    return ctx.allowed_student_ids


def _require_student(ctx: McpPrincipal, student_id: Optional[int], what: str) -> None:
    """`ensure_student_access`, phrased for an agent instead of as an HTTP 403."""
    if not ctx.may_see_student(student_id):
        raise ValueError(
            f"Student {student_id} is not on your caseload, so {what} is not "
            f"available. Call list_students to see who is."
        )


def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date like 2026-05-14 (got {value!r})") from exc


def _parse_datetime(value: Optional[str], field: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        parsed = _parse_date(value, field)
        return datetime.combine(parsed, datetime.min.time()) if parsed else None


def _student_label(student: Optional[Student], ctx: McpPrincipal) -> str:
    """
    The identity an agent prints for a student: the alias, always.

    No caller branch, deliberately. `ctx` stays in the signature because every
    call site has one and a future policy may want it, but there is no
    condition under which this returns a name.
    """
    if student is None:
        return "Unknown"
    return student.alias


def _student_identity(payload: dict, student: Student) -> dict:
    """
    Rewrite a serialized student so the ALIAS is the display identity.

    Belt: the recursive sanitizer would strip `first`, `last`, `uic` and
    `date_of_birth` out of this payload anyway. Braces: doing it at the source
    means the agent gets a clean object with an obvious identity field rather
    than a record with holes where the names used to be, and the difference
    shows in how an agent talks about the student.
    """
    for key in ("first", "last", "uic", "date_of_birth", "dateOfBirth"):
        payload.pop(key, None)
    alias = student.alias
    payload["alias"] = alias
    payload["displayName"] = alias
    return payload


def _load_goal(db: Session, ctx: McpPrincipal, goal_id: int) -> IEPGoal:
    goal = db.query(IEPGoal).filter(IEPGoal.id == goal_id).first()
    if goal is None:
        raise ValueError(
            f"No goal with id {goal_id}. Call list_goals for the ids that exist."
        )
    _require_student(ctx, goal.student_id, f"goal {goal_id}")
    return goal


def _load_objective(db: Session, ctx: McpPrincipal, objective_id: int) -> GoalObjective:
    objective = db.query(GoalObjective).filter(GoalObjective.id == objective_id).first()
    if objective is None:
        raise ValueError(
            f"No objective with id {objective_id}. Call list_objectives for a "
            f"goal to see the ids that exist."
        )
    _require_student(ctx, objective.goal.student_id, f"objective {objective_id}")
    return objective


def _load_entry(db: Session, ctx: McpPrincipal, entry_id: int) -> ObjectiveProgressEntry:
    entry = (
        db.query(ObjectiveProgressEntry)
        .filter(ObjectiveProgressEntry.id == entry_id)
        .first()
    )
    if entry is None:
        raise ValueError(
            f"No progress entry with id {entry_id}. Call list_progress_entries "
            f"for an objective to see the ids that exist."
        )
    _require_student(ctx, entry.objective.goal.student_id, f"progress entry {entry_id}")
    return entry


def _load_session(db: Session, ctx: McpPrincipal, session_id: int) -> TherapySession:
    row = db.query(TherapySession).filter(TherapySession.id == session_id).first()
    if row is None:
        raise ValueError(
            f"No therapy session with id {session_id}. Call "
            f"list_therapy_sessions for the ids that exist."
        )
    _require_student(ctx, row.student_id, f"therapy session {session_id}")
    return row


# --------------------------------------------------------------------------
# read tools
# --------------------------------------------------------------------------
@tool()
def get_caseload_overview() -> dict:
    """
    Start here. Returns who this connection key belongs to and a snapshot of
    the caseload behind it: how many students by enrollment status, how many
    IEP goals by status, how much progress has been logged recently, and what
    is on the schedule over the next week.

    Nothing here takes an argument — the caseload is fixed by the key. Use it
    to decide which of the list_* tools to call next, and to sanity-check that
    you are looking at the therapist you think you are.
    """
    db = _session()
    try:
        ctx = _ctx()
        students = StudentRepository(db).list_students(
            include_archived=True, allowed_student_ids=_scope_ids(ctx)
        )
        visible = [s for s in students if ctx.may_see_student(s.id)]
        active = [s for s in visible if not s.is_archived]
        ids = [s.id for s in visible]

        by_status: dict[str, int] = {}
        for student in active:
            key = student.enrollment_status or "Unknown"
            by_status[key] = by_status.get(key, 0) + 1

        goals = (
            db.query(IEPGoal).filter(IEPGoal.student_id.in_(ids)).all() if ids else []
        )
        goals_by_status: dict[str, int] = {}
        for goal in goals:
            key = goal.goal_status or "Unknown"
            goals_by_status[key] = goals_by_status.get(key, 0) + 1

        today = date.today()
        recent_cutoff = today - timedelta(days=30)
        recent_entries = (
            db.query(ObjectiveProgressEntry)
            .join(GoalObjective, ObjectiveProgressEntry.objective_id == GoalObjective.id)
            .join(IEPGoal, GoalObjective.goal_id == IEPGoal.id)
            .filter(IEPGoal.student_id.in_(ids))
            .filter(ObjectiveProgressEntry.progress_date >= recent_cutoff)
            .count()
            if ids
            else 0
        )

        appointments = AppointmentRepository(db).get_appointments_by_date_range(
            start_date=today, end_date=today + timedelta(days=7)
        )
        upcoming = [a for a in appointments if a.student_id in set(ids)]

        reviews_due = [
            {
                "studentId": s.id,
                "student": _student_label(s, ctx),
                "annualReviewDue": s.annual_review_due_date.isoformat(),
                "daysUntil": s.days_until_annual_review,
            }
            for s in active
            if s.annual_review_due_date
            and s.annual_review_due_date <= today + timedelta(days=60)
        ]

        return {
            "therapist": ctx.user_name,
            "role": ctx.role,
            "accessMode": ctx.access_mode,
            "students": {
                "total": len(visible),
                "active": len(active),
                "archived": len(visible) - len(active),
                "byEnrollmentStatus": by_status,
            },
            "goals": {"total": len(goals), "byStatus": goals_by_status},
            "progressEntriesLast30Days": recent_entries,
            "upcomingWeek": {
                "appointments": len(upcoming),
                "next": [
                    {
                        "appointmentId": a.id,
                        "studentId": a.student_id,
                        "student": _student_label(a.student, ctx),
                        "start": a.start_datetime.isoformat() if a.start_datetime else None,
                        "end": a.end_datetime.isoformat() if a.end_datetime else None,
                        "type": a.appointment_type,
                        "status": a.status,
                    }
                    for a in upcoming[:10]
                ],
            },
            "annualReviewsDueWithin60Days": sorted(
                reviews_due, key=lambda r: r["annualReviewDue"]
            ),
        }
    finally:
        db.close()


@tool()
def list_students(
    enrollment_status: Optional[str] = None,
    include_archived: bool = False,
) -> list[dict]:
    """
    Every student on this caseload, as lightweight summaries (id, alias,
    grade, enrollment status, assigned teacher and case manager).

    Each row identifies its student by `alias`/`displayName` ("student_12") —
    that is the identity you use when you talk about them. Real names, dates of
    birth and UICs are not part of this response and cannot be requested.

    `enrollment_status` filters on the app's own values, typically "Active".
    `include_archived` brings back students who were archived — archived means
    hidden from working lists, never deleted, and their goals and history are
    all still readable.

    The `id` of each row is the `student_id` every other tool wants. For the
    full record — IEP dates, school, eligibilities — call get_student with it.
    """
    db = _session()
    try:
        ctx = _ctx()
        rows = StudentRepository(db).list_students(
            enrollment_status=enrollment_status,
            include_archived=include_archived,
            allowed_student_ids=_scope_ids(ctx),
        )
        rows = [s for s in rows if ctx.may_see_student(s.id)]
        return [_student_identity(_dump(StudentSummary, student), student) for student in rows]
    finally:
        db.close()


@tool()
def get_student(student_id: int) -> dict:
    """
    One student's full record: alias, grade, enrollment status, assigned
    school, teacher and case manager, every IEP date the app tracks (current
    IEP, annual review due, re-evaluation due, meeting, initial evaluation,
    eligibility determination) and the disability categories the student
    qualifies under.

    The student is identified by `alias`/`displayName` ("student_12"). Name,
    date of birth and UIC are deliberately absent — they are not served over
    this connection.

    `student_id` comes from list_students. Pair with list_goals(student_id) for
    what the student is actually working on.
    """
    db = _session()
    try:
        ctx = _ctx()
        _require_student(ctx, student_id, "this student")
        student = StudentRepository(db).get_student_by_id(student_id)
        if student is None:
            raise ValueError(
                f"No student with id {student_id}. Call list_students for the "
                f"ids that exist."
            )
        return _student_identity(_dump(StudentRead, student), student)
    finally:
        db.close()


@tool()
def list_goals(
    student_id: Optional[int] = None,
    goal_status: Optional[str] = None,
) -> list[dict]:
    """
    IEP goals, optionally narrowed to one student and/or one status.

    A goal is the year-long target ("will produce /r/ in conversation with 80%
    accuracy"); the measurable steps under it are OBJECTIVES, and the data
    logged against those steps are PROGRESS ENTRIES. `goal_status` is the app's
    own vocabulary — "Active" and "Mastered" are the common ones.

    Omit `student_id` to sweep the whole caseload. Each row's `id` is the
    `goal_id` for get_goal, list_objectives, update_goal and delete_goal.
    """
    db = _session()
    try:
        ctx = _ctx()
        if student_id is not None:
            _require_student(ctx, student_id, "goals for this student")
        goals = GoalRepository(db).get_goals(
            student_id=student_id, goal_status=goal_status
        )
        goals = [g for g in goals if ctx.may_see_student(g.student_id)]
        return _dump_many(IEPGoalRead, goals)
    finally:
        db.close()


@tool()
def get_goal(goal_id: int) -> dict:
    """
    One IEP goal WITH its objectives and each objective's progress entries —
    the whole tree under a goal in a single call.

    Use this rather than list_objectives + list_progress_entries when you want
    to reason about a goal as a whole (is it on track, which objective is
    lagging). `goal_id` comes from list_goals.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_goal(db, ctx, goal_id)
        goal = GoalRepository(db).get_goal_by_id(goal_id)
        payload = _dump(IEPGoalWithObjectives, goal)
        payload["goal_category_name"] = (
            goal.goal_category.name if goal.goal_category else None
        )
        return payload
    finally:
        db.close()


@tool()
def list_objectives(goal_id: int) -> list[dict]:
    """
    The objectives under one goal, in objective_number order, each with its
    progress entries and its latest entry.

    An objective is the thing data is actually collected against; its `id` is
    the `objective_id` that list_progress_entries, create_progress_entry and
    update_objective want. `goal_id` comes from list_goals.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_goal(db, ctx, goal_id)
        rows = ObjectiveRepository(db).get_goal_objectives(goal_id)
        return _dump_many(GoalObjectiveWithProgress, rows)
    finally:
        db.close()


@tool()
def list_progress_entries(
    objective_id: int,
    progress_date_from: Optional[str] = None,
    progress_date_to: Optional[str] = None,
) -> list[dict]:
    """
    The progress entries logged against one objective, newest first.

    A progress entry is one dated observation: what the student did
    (`progress_on_objective`), the clinician's notes, initials, and the kind of
    session it came from. This is the running record a progress report is
    written from.

    `objective_id` comes from list_objectives. The two date bounds are ISO
    dates and are inclusive; omit them for the whole history.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_objective(db, ctx, objective_id)
        rows = ProgressEntryRepository(db).get_progress_entries(
            objective_id=objective_id,
            progress_date_from=_parse_date(progress_date_from, "progress_date_from"),
            progress_date_to=_parse_date(progress_date_to, "progress_date_to"),
        )
        return _dump_many(ObjectiveProgressEntryRead, rows)
    finally:
        db.close()


@tool()
def list_therapy_sessions(
    student_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Therapy sessions as summaries: when, with whom, how long, and what state
    they are in ("planned", "in_progress", "completed", "cancelled",
    "no_show").

    A session is a sitting of therapy — distinct from an APPOINTMENT, which is
    the slot on the calendar. A session may be linked to an appointment or be
    unscheduled. For what was actually worked on, call get_therapy_session with
    the row's `id`.

    Dates are ISO and inclusive. Omit `student_id` to sweep the caseload.
    """
    db = _session()
    try:
        ctx = _ctx()
        if student_id is not None:
            _require_student(ctx, student_id, "therapy sessions for this student")
        filters = TherapySessionFilters(
            student_id=student_id,
            status=status,
            start_date=_parse_date(start_date, "start_date"),
            end_date=_parse_date(end_date, "end_date"),
        )
        rows = TherapySessionRepository(db).get_sessions(
            filters, skip=0, limit=max(1, min(int(limit), 500))
        )
        rows = [s for s in rows if ctx.may_see_student(s.student_id)]
        shim = _AuthShim(ctx)
        return [
            _build_session_summary(row, shim).model_dump(exclude_none=True, mode="json")
            for row in rows
        ]
    finally:
        db.close()


@tool()
def get_therapy_session(session_id: int) -> dict:
    """
    One therapy session in full: timings, notes, clinical observations, the
    goals planned for it and the objectives worked in it — including trials
    attempted and correct, independence level, prompt level and whether the
    objective was met.

    This is where the raw data behind a session lives. `session_id` comes from
    list_therapy_sessions or get_schedule.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_session(db, ctx, session_id)
        row = TherapySessionRepository(db).get_session_by_id(
            session_id, include_details=True
        )
        return _build_session_response(row, _AuthShim(ctx)).model_dump(
            exclude_none=True, mode="json"
        )
    finally:
        db.close()


@tool()
def get_schedule(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    The calendar: individual APPOINTMENTS and group TIME BLOCKS in a date
    range, both in start-time order.

    An appointment is one student in one slot; a time block is a group slot
    with several students assigned to it. Both may already have a therapy
    session attached — `therapySessionId` tells you which, and
    get_therapy_session opens it.

    Defaults to today through six days out (a working week) when no dates are
    given. Only appointments for students on your caseload are returned; a
    group block is returned with its roster filtered the same way.
    """
    db = _session()
    try:
        ctx = _ctx()
        begin = _parse_date(start_date, "start_date") or date.today()
        finish = _parse_date(end_date, "end_date") or (begin + timedelta(days=6))
        if finish < begin:
            raise ValueError("end_date must not be before start_date")

        appointments = AppointmentRepository(db).get_appointments_by_date_range(
            start_date=begin, end_date=finish
        )
        appointments = [a for a in appointments if ctx.may_see_student(a.student_id)]

        blocks = TimeBlockRepository(db).get_time_blocks_by_date_range(
            start_date=begin, end_date=finish
        )

        return {
            "startDate": begin.isoformat(),
            "endDate": finish.isoformat(),
            "appointments": [
                {
                    "appointmentId": a.id,
                    "studentId": a.student_id,
                    "student": _student_label(a.student, ctx),
                    "teacher": a.teacher.full_name if a.teacher else None,
                    "school": a.school.name if a.school else None,
                    "start": a.start_datetime.isoformat() if a.start_datetime else None,
                    "end": a.end_datetime.isoformat() if a.end_datetime else None,
                    "durationMinutes": a.duration_minutes,
                    "type": a.appointment_type,
                    "status": a.status,
                    "location": a.location,
                    "timeBlockId": a.time_block_id,
                    "therapySessionId": a.therapy_session.id if a.therapy_session else None,
                    "therapySessionStatus": (
                        a.therapy_session.status if a.therapy_session else None
                    ),
                    "notes": a.notes,
                }
                for a in appointments
            ],
            "timeBlocks": [
                {
                    "timeBlockId": b.id,
                    "title": b.title,
                    "blockType": b.block_type,
                    "start": b.start_datetime.isoformat() if b.start_datetime else None,
                    "end": b.end_datetime.isoformat() if b.end_datetime else None,
                    "durationMinutes": b.duration_minutes,
                    "status": b.status,
                    "location": b.location,
                    "teacher": b.teacher.full_name if b.teacher else None,
                    "school": b.school.name if b.school else None,
                    "students": [
                        {
                            "studentId": assignment.student.id,
                            "student": _student_label(assignment.student, ctx),
                        }
                        for assignment in b.block_assignments
                        if assignment.status == "assigned"
                        and assignment.student is not None
                        and ctx.may_see_student(assignment.student.id)
                    ],
                }
                for b in blocks
            ],
        }
    finally:
        db.close()


@tool()
def list_schools() -> list[dict]:
    """
    The active schools this practice serves, with their student and teacher
    counts. A school `id` is what `school_id` means on a student.
    """
    db = _session()
    try:
        _ctx()
        return _dump_many(SchoolSummary, SchoolRepository(db).get_active_schools_summary())
    finally:
        db.close()


@tool()
def list_teachers() -> list[dict]:
    """
    The active teachers and support staff, with their display names.

    A teacher `id` is what `teacher_id` and `case_manager_id` mean on a
    student: the classroom teacher, and the person who owns the student's IEP
    paperwork. They are frequently the same person.
    """
    db = _session()
    try:
        _ctx()
        return _dump_many(TeacherSummary, TeacherRepository(db).get_active_teachers_summary())
    finally:
        db.close()


@tool()
def list_eligibility_categories() -> list[dict]:
    """
    The disability categories a student can be found eligible under (the state
    vocabulary — "Speech and Language Impairment", "Autism Spectrum Disorder"
    and so on).

    A student's own eligibilities come back inside get_student; this is the
    list of what exists.
    """
    db = _session()
    try:
        _ctx()
        return _dump_many(
            EligibilityCategoryRead, EligibilityRepository(db).get_all_categories(active_only=True)
        )
    finally:
        db.close()


@tool()
def list_goal_categories() -> list[dict]:
    """
    The goal categories every IEP goal must be filed under (articulation,
    language, fluency, and so on).

    Fetch this BEFORE create_goal: `goal_category_id` is required there and
    guessing it is how a goal ends up in the wrong section of a progress report.
    """
    db = _session()
    try:
        _ctx()
        return _dump_many(
            GoalCategoryRead, GoalCategoryRepository(db).get_all_categories(active_only=True)
        )
    finally:
        db.close()


# --------------------------------------------------------------------------
# write tools
# --------------------------------------------------------------------------
@tool()
def create_progress_entry(
    objective_id: int,
    progress_date: str,
    progress_on_objective: Optional[str] = None,
    progress_comments: Optional[str] = None,
    therapist_initials: Optional[str] = None,
    session_type: Optional[str] = None,
) -> dict:
    """
    WRITE. Logs one dated progress observation against an objective — the
    everyday act of data collection in this app.

    `progress_date` is the date the data was TAKEN, not today, and is required.
    `progress_on_objective` is the short measured result the app prints in
    progress reports ("8/10 trials", "70% accuracy"); `progress_comments` is
    the narrative. `therapist_initials` is how the entry is attributed on
    paper.

    `objective_id` comes from list_objectives. Say what you are logging, for
    which student, before you call this — it becomes part of a clinical record.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_objective(db, ctx, objective_id)
        payload = ObjectiveProgressEntryCreate(
            objective_id=objective_id,
            progress_date=_parse_date(progress_date, "progress_date"),
            progress_on_objective=progress_on_objective,
            progress_comments=progress_comments,
            therapist_initials=therapist_initials,
            session_type=session_type,
        )
        row = ProgressEntryRepository(db).create_progress_entry(payload.model_dump())
        return _dump(ObjectiveProgressEntryRead, row)
    finally:
        db.close()


@tool()
def update_progress_entry(
    entry_id: int,
    progress_date: Optional[str] = None,
    progress_on_objective: Optional[str] = None,
    progress_comments: Optional[str] = None,
    therapist_initials: Optional[str] = None,
    session_type: Optional[str] = None,
) -> dict:
    """
    WRITE. Corrects an existing progress entry. Only the arguments you pass are
    changed; anything omitted is left exactly as it was.

    `entry_id` comes from list_progress_entries. To remove an entry entirely
    use delete_progress_entry, which refuses without confirm=true.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_entry(db, ctx, entry_id)
        changes = {
            "progress_date": _parse_date(progress_date, "progress_date"),
            "progress_on_objective": progress_on_objective,
            "progress_comments": progress_comments,
            "therapist_initials": therapist_initials,
            "session_type": session_type,
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            raise ValueError("Nothing to update — pass at least one field to change.")
        validated = ObjectiveProgressEntryUpdate(**changes).model_dump(exclude_unset=True)
        row = ProgressEntryRepository(db).update_progress_entry(entry_id, validated)
        return _dump(ObjectiveProgressEntryRead, row)
    finally:
        db.close()


@tool()
def create_goal(
    student_id: int,
    goal_category_id: int,
    goal_description: str,
    target_criteria: str,
    start_date: str,
    goal_number: Optional[str] = None,
    target_behavior: Optional[str] = None,
    baseline_data: Optional[str] = None,
    goal_status: str = "Active",
    end_date: Optional[str] = None,
) -> dict:
    """
    WRITE. Adds an IEP goal to a student.

    `goal_description` is the goal as it is written in the IEP;
    `target_criteria` is the mastery bar ("80% accuracy across 3 sessions") and
    is required, because a goal nobody can score is not a goal.
    `goal_category_id` must come from list_goal_categories. `start_date` is
    when the goal period begins.

    A new goal has no objectives yet — follow with create_objective for each
    measurable step, then progress entries go against those objectives, never
    against the goal.
    """
    db = _session()
    try:
        ctx = _ctx()
        _require_student(ctx, student_id, "creating a goal for this student")
        payload = IEPGoalCreate(
            student_id=student_id,
            goal_category_id=goal_category_id,
            goal_number=goal_number,
            goal_description=goal_description,
            target_behavior=target_behavior,
            baseline_data=baseline_data,
            target_criteria=target_criteria,
            goal_status=goal_status,
            start_date=_parse_date(start_date, "start_date"),
            end_date=_parse_date(end_date, "end_date"),
        )
        row = GoalRepository(db).create_goal(payload)
        return _dump(IEPGoalRead, row)
    finally:
        db.close()


@tool()
def update_goal(
    goal_id: int,
    goal_category_id: Optional[int] = None,
    goal_number: Optional[str] = None,
    goal_description: Optional[str] = None,
    target_behavior: Optional[str] = None,
    baseline_data: Optional[str] = None,
    target_criteria: Optional[str] = None,
    goal_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    mastery_date: Optional[str] = None,
) -> dict:
    """
    WRITE. Edits an IEP goal. Only the arguments you pass are changed.

    Marking a goal mastered is two fields, not one: set `goal_status` to
    "Mastered" AND `mastery_date` to the date it was met — the app reads the
    date, and a status without one leaves the goal looking unfinished on a
    report. `goal_id` comes from list_goals.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_goal(db, ctx, goal_id)
        changes = {
            "goal_category_id": goal_category_id,
            "goal_number": goal_number,
            "goal_description": goal_description,
            "target_behavior": target_behavior,
            "baseline_data": baseline_data,
            "target_criteria": target_criteria,
            "goal_status": goal_status,
            "start_date": _parse_date(start_date, "start_date"),
            "end_date": _parse_date(end_date, "end_date"),
            "mastery_date": _parse_date(mastery_date, "mastery_date"),
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            raise ValueError("Nothing to update — pass at least one field to change.")
        row = GoalRepository(db).update_goal(goal_id, IEPGoalUpdate(**changes))
        return _dump(IEPGoalRead, row)
    finally:
        db.close()


@tool()
def create_objective(
    goal_id: int,
    objective_number: int,
    objective_description: str,
    progress_status: Optional[str] = None,
    schedule_frequency: Optional[str] = None,
) -> dict:
    """
    WRITE. Adds a measurable objective (a "short-term objective" / benchmark)
    under an existing goal.

    `objective_number` is its position under the goal, 1-10, and must be unique
    within the goal — call list_objectives first and take the next free number.
    `schedule_frequency` is how often data is meant to be taken ("weekly",
    "monthly"), which is what drives the app's reminders.

    Progress entries attach to objectives, so a goal with no objectives can
    never accumulate data.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_goal(db, ctx, goal_id)
        existing = ObjectiveRepository(db).get_goal_objectives(goal_id)
        taken = sorted(o.objective_number for o in existing)
        if objective_number in taken:
            raise ValueError(
                f"Goal {goal_id} already has objective number {objective_number}. "
                f"Numbers in use: {taken}."
            )
        payload = {
            "goal_id": goal_id,
            "objective_number": objective_number,
            "objective_description": objective_description,
            "progress_status": progress_status,
            "schedule_frequency": schedule_frequency,
        }
        row = ObjectiveRepository(db).create_objective(payload)
        return _dump(GoalObjectiveRead, row)
    finally:
        db.close()


@tool()
def update_objective(
    objective_id: int,
    objective_description: Optional[str] = None,
    progress_status: Optional[str] = None,
    schedule_frequency: Optional[str] = None,
) -> dict:
    """
    WRITE. Edits an objective's wording, its current progress status, or how
    often data is meant to be collected. Only what you pass is changed.

    The objective's NUMBER is deliberately not editable here — renumbering
    reorders a printed IEP and is done in the app. `objective_id` comes from
    list_objectives.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_objective(db, ctx, objective_id)
        changes = {
            "objective_description": objective_description,
            "progress_status": progress_status,
            "schedule_frequency": schedule_frequency,
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            raise ValueError("Nothing to update — pass at least one field to change.")
        validated = GoalObjectiveUpdate(**changes).model_dump(exclude_unset=True)
        row = ObjectiveRepository(db).update_objective(objective_id, validated)
        return _dump(GoalObjectiveRead, row)
    finally:
        db.close()


@tool()
def create_therapy_session(
    student_id: int,
    session_date: str,
    session_type: str = "individual",
    status: str = "planned",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    planned_duration_minutes: Optional[int] = 30,
    prep_notes: Optional[str] = None,
    appointment_id: Optional[int] = None,
    planned_goal_ids: Optional[list[int]] = None,
    planned_objective_ids: Optional[list[int]] = None,
) -> dict:
    """
    WRITE. Creates a therapy session record for a student — the sitting itself,
    not the calendar slot.

    `session_date` is required (ISO date or datetime). `status` starts at
    "planned"; complete_therapy_session is what closes it out. Pass
    `appointment_id` to attach the session to an existing calendar slot from
    get_schedule; leave it out for an unscheduled or make-up session.

    `planned_goal_ids` and `planned_objective_ids` pre-load what you intend to
    work on — every id is checked against this student, so an objective that
    belongs to somebody else is refused rather than silently attached.
    """
    db = _session()
    try:
        ctx = _ctx()
        _require_student(ctx, student_id, "creating a therapy session for this student")

        goal_rows = []
        for goal_id in planned_goal_ids or []:
            goal = _load_goal(db, ctx, goal_id)
            if goal.student_id != student_id:
                raise ValueError(
                    f"Goal {goal_id} belongs to student {goal.student_id}, not "
                    f"student {student_id}."
                )
            goal_rows.append({"goal_id": goal_id, "planned": True, "priority": 1})

        objective_rows = []
        for objective_id in planned_objective_ids or []:
            objective = _load_objective(db, ctx, objective_id)
            if objective.goal.student_id != student_id:
                raise ValueError(
                    f"Objective {objective_id} belongs to student "
                    f"{objective.goal.student_id}, not student {student_id}."
                )
            objective_rows.append(
                {
                    "objective_id": objective_id,
                    "goal_id": objective.goal_id,
                    "planned": True,
                    "priority": 1,
                }
            )

        payload = TherapySessionCreate(
            student_id=student_id,
            appointment_id=appointment_id,
            session_date=_parse_datetime(session_date, "session_date"),
            start_time=_parse_datetime(start_time, "start_time"),
            end_time=_parse_datetime(end_time, "end_time"),
            planned_duration_minutes=planned_duration_minutes,
            session_type=session_type,
            status=status,
            created_from="manual",
            prep_notes=prep_notes,
            planned_goals=goal_rows,
            planned_objectives=objective_rows,
        )
        row = TherapySessionRepository(db).create_session(payload)
        detailed = TherapySessionRepository(db).get_session_by_id(
            row.id, include_details=True
        )
        return _build_session_response(detailed, _AuthShim(ctx)).model_dump(
            exclude_none=True, mode="json"
        )
    finally:
        db.close()


@tool()
def complete_therapy_session(
    session_id: int,
    session_notes: Optional[str] = None,
    therapist_observations: Optional[str] = None,
    student_engagement: Optional[str] = None,
    materials_used: Optional[str] = None,
    goals_addressed: bool = False,
    session_quality: Optional[str] = None,
    follow_up_needed: bool = False,
    follow_up_notes: Optional[str] = None,
) -> dict:
    """
    WRITE. Closes out a therapy session exactly as the app's "complete" button
    does: status becomes "completed", the end time is stamped now, the actual
    duration is computed, and any linked appointment is marked completed with
    the same notes.

    `student_engagement` is one of high / medium / low / variable;
    `session_quality` is excellent / good / fair / poor. Set
    `goals_addressed=true` when the planned goals were actually worked.

    This does NOT write progress entries — per-objective data is its own
    record. Use create_progress_entry for that.
    """
    db = _session()
    try:
        ctx = _ctx()
        _load_session(db, ctx, session_id)
        request = CompleteSessionRequest(
            session_notes=session_notes,
            therapist_observations=therapist_observations,
            student_engagement=student_engagement,
            materials_used=materials_used,
            goals_addressed=goals_addressed,
            session_quality=session_quality,
            follow_up_needed=follow_up_needed,
            follow_up_notes=follow_up_notes,
        )
        row = TherapySessionRepository(db).complete_session(session_id, request)
        detailed = TherapySessionRepository(db).get_session_by_id(
            row.id, include_details=True
        )
        return _build_session_response(detailed, _AuthShim(ctx)).model_dump(
            exclude_none=True, mode="json"
        )
    finally:
        db.close()


@tool()
def update_student(
    student_id: int,
    grade_level: Optional[str] = None,
    enrollment_status: Optional[str] = None,
    school_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    case_manager_id: Optional[int] = None,
    iep_date: Optional[str] = None,
    annual_review_due_date: Optional[str] = None,
    reevaluation_due_date: Optional[str] = None,
    iep_meeting_date: Optional[str] = None,
    initial_evaluation_date: Optional[str] = None,
    eligibility_determination_date: Optional[str] = None,
) -> dict:
    """
    WRITE. Updates the administrative side of a student's record: grade,
    enrollment status, school, assigned teacher and case manager, and the six
    IEP dates the app tracks. Only what you pass is changed.

    Names, date of birth and UIC are NOT editable here, and are not returned
    here either — a student's identity is changed in the app, where it can be
    checked against the district's own records. `school_id` comes from list_schools; `teacher_id` and
    `case_manager_id` from list_teachers.

    Moving `annual_review_due_date` or `reevaluation_due_date` moves a legal
    compliance deadline, so confirm the new date with a human first.
    """
    db = _session()
    try:
        ctx = _ctx()
        _require_student(ctx, student_id, "updating this student")
        changes: dict[str, Any] = {
            "grade_level": grade_level,
            "enrollment_status": enrollment_status,
            "school_id": school_id,
            "teacher_id": teacher_id,
            "case_manager_id": case_manager_id,
            "iep_date": _parse_date(iep_date, "iep_date"),
            "annual_review_due_date": _parse_date(
                annual_review_due_date, "annual_review_due_date"
            ),
            "reevaluation_due_date": _parse_date(
                reevaluation_due_date, "reevaluation_due_date"
            ),
            "iep_meeting_date": _parse_date(iep_meeting_date, "iep_meeting_date"),
            "initial_evaluation_date": _parse_date(
                initial_evaluation_date, "initial_evaluation_date"
            ),
            "eligibility_determination_date": _parse_date(
                eligibility_determination_date, "eligibility_determination_date"
            ),
        }
        changes = {k: v for k, v in changes.items() if v is not None}
        if not changes:
            raise ValueError("Nothing to update — pass at least one field to change.")
        row = StudentRepository(db).update_student(
            student_id,
            StudentUpdate(**changes),
            allowed_student_ids=_scope_ids(ctx),
        )
        if row is None:
            raise ValueError(f"No student with id {student_id} on your caseload.")
        return _student_identity(_dump(StudentRead, row), row)
    finally:
        db.close()


# --------------------------------------------------------------------------
# destructive tools — both refuse without confirm=true
# --------------------------------------------------------------------------
@tool()
def delete_progress_entry(entry_id: int, confirm: bool = False) -> dict:
    """
    WRITE — DESTRUCTIVE. Permanently removes one progress entry.

    There is no undo and no archive: the observation, its date, its notes and
    its attribution are gone, and if it was the only data taken that week the
    gap is simply a gap on the next progress report.

    `confirm` must be literally true. Anything else — false, "yes", omitted —
    refuses and deletes nothing, and returns a summary of what WOULD have gone,
    so a record can never disappear because a tool call was half-formed. Show
    that summary to a human and get an answer before you send confirm=true.

    `entry_id` comes from list_progress_entries. To fix a wrong value, prefer
    update_progress_entry.
    """
    db = _session()
    try:
        ctx = _ctx()
        entry = _load_entry(db, ctx, entry_id)
        objective = entry.objective
        goal = objective.goal
        summary = {
            "entryId": entry.id,
            "progressDate": entry.progress_date.isoformat() if entry.progress_date else None,
            "progressOnObjective": entry.progress_on_objective,
            "comments": entry.progress_comments,
            "therapistInitials": entry.therapist_initials,
            "objectiveId": objective.id,
            "objectiveNumber": objective.objective_number,
            "goalId": goal.id,
            "studentId": goal.student_id,
        }
        if confirm is not True:
            return {
                "deleted": False,
                "reason": "confirm must be true to delete this progress entry",
                "wouldDelete": summary,
            }
        ProgressEntryRepository(db).delete_progress_entry(entry_id)
        return {"deleted": True, "removed": summary}
    finally:
        db.close()


@tool()
def delete_goal(goal_id: int, confirm: bool = False) -> dict:
    """
    WRITE — DESTRUCTIVE, AND THE WIDEST-REACHING TOOL HERE. Permanently removes
    an IEP goal AND EVERYTHING UNDER IT: every objective, and every progress
    entry ever logged against those objectives.

    That history is the evidence a school has that services were delivered.
    Nothing else records it, and it cannot be recovered. In almost every case
    the thing you actually want is update_goal with goal_status="Mastered" or
    "Discontinued", which keeps the record and stops the goal appearing as
    active work.

    `confirm` must be literally true. Without it this deletes nothing and
    instead returns a count of the objectives and entries that would go — show
    that to a human and get an answer before sending confirm=true.

    `goal_id` comes from list_goals.
    """
    db = _session()
    try:
        ctx = _ctx()
        goal = _load_goal(db, ctx, goal_id)
        objectives = list(goal.objectives or [])
        summary = {
            "goalId": goal.id,
            "studentId": goal.student_id,
            "goalNumber": goal.goal_number,
            "goalDescription": goal.goal_description,
            "goalStatus": goal.goal_status,
            "objectives": len(objectives),
            "progressEntries": sum(
                len(o.progress_entries or []) for o in objectives
            ),
            "objectiveNumbers": sorted(o.objective_number for o in objectives),
        }
        if confirm is not True:
            return {
                "deleted": False,
                "reason": "confirm must be true to delete this goal and everything under it",
                "wouldDelete": summary,
            }
        GoalRepository(db).delete_goal(goal_id)
        return {"deleted": True, "removed": summary}
    finally:
        db.close()


# Installed after every tool is registered, because it wraps the manager those
# registrations populate. Order does not actually matter (it wraps the method,
# not the table), but reading it here says the filter is over a finished
# server rather than a half-built one.
_install_sdk_error_filter()

# The ASGI application the middleware hands authenticated requests to. Built at
# import time so `main.py` can register it before the app starts serving.
mcp_asgi_app = mcp_server.streamable_http_app()
