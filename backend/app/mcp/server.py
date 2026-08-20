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
from app.models.archive_event import ARCHIVABLE_ENTITY_TYPES
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.models.student import Student
from app.models.import_batch import ImportBatch
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
from app.services import archive as archive_service
from app.services import blind_import
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
from app.settings import settings

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
before you write it.

NOTHING YOU CAN DO OVER THIS CONNECTION DESTROYS CLINICAL DATA. There is no
delete tool for a student, a goal, an objective, a progress entry or a session
— there are archive_* tools, and archiving HIDES a record from working lists
while keeping every field of it. Each archive is one event with an id;
list_archive_events shows those events and restore_archived(event_id,
confirm=true) puts every row of one back. The archive_* tools still require
confirm=true, and still show you the count of what they will hide first,
because a therapist should know that her caseload is about to lose a goal — but
the answer to "did I just lose that data" is always no.

Archiving cascades DOWNWARD and only over records that are currently active:
archive_goal hides the goal, its objectives and their progress entries;
archive_student hides everything on that student. An objective archived last
term keeps its own older event and is NOT swept into a new one, so restoring
the new event never resurrects work that was retired on purpose.

The ONE tool here that destroys anything is discard_import, and what it
destroys is a staged upload, never a caseload record — see below.

Two vocabularies are worth fetching before you write: list_goal_categories
(every goal must name one) and list_eligibility_categories (the disability
categories a student qualifies under).

Dates are ISO-8601 strings: "2026-05-14" for a date, "2026-05-14T10:30:00" for
a time.

NEVER ACCEPT A PASTED ROSTER. If a therapist pastes spreadsheet rows, a list of
students, a CSV, a screenshot of a caseload, or "here are my kids" in any form
into this conversation, do not work with it. Say plainly that you should not be
handling children's names and birthdays in a chat window, and give her an
upload link instead: call create_import_upload and hand her the URL. This is
not a preference. A pasted roster is a permanent copy of identified student
data in a transcript store, and the import tools exist precisely so that no
such copy is ever made.

IMPORTING A CASELOAD FROM A SPREADSHEET OF ANY LAYOUT works like this, and the
design is that YOU NEVER SEE THE DATA:

  1. create_import_upload gives you a one-shot, 30-minute URL. The therapist
     opens it in her own browser and uploads the .xlsx or .csv. The file goes
     from her machine to the server without passing through you.
  2. get_import_preview shows you the file's SHAPE and nothing else: every cell
     masked as "Xxxxxxx" or "##/##/####", per-column counts, and the header
     text. That is enough to work out what each column is.
  3. set_import_mapping is where you say which column means what. Only then,
     and only for columns mapped to school, teacher, case_manager, grade_level,
     enrollment_status, the three IEP dates or eligibility, do real sample
     values come back. Names, dates of birth, UICs and free-text notes stay
     masked no matter what they are mapped to and no matter how you ask.
  4. validate_import reports problems by ROW NUMBER, with the offending value
     only where that value is a school or a teacher — the things you are meant
     to reconcile against list_schools and list_teachers.
  5. commit_import (confirm=true) creates the students from the stored file and
     hands you back aliases, never names.
  6. discard_import (confirm=true) destroys the staged copy. Offer it as soon
     as the import is done. This is the one irreversible tool on the server and
     it is meant to be — what it destroys is a verbatim copy of somebody's
     roster export, not a caseload record.

Work with the therapist at every step: propose the mapping in plain language
and let her correct it. She can see the spreadsheet; you cannot, and that is
the arrangement working, not a limitation to route around.
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


# The four loaders below EXCLUDE ARCHIVED ROWS by default. An archived record
# is hidden from every list tool, so a tool that could still fetch one by id
# would be a second, unlisted way in -- and the agent would have no way to tell
# a live goal from a retired one. `include_archived=True` is passed by exactly
# one family of callers: the archive_* tools, which have to see an archived row
# in order to say "already archived" rather than "no such id".
def _load_goal(
    db: Session, ctx: McpPrincipal, goal_id: int, include_archived: bool = False
) -> IEPGoal:
    query = db.query(IEPGoal).filter(IEPGoal.id == goal_id)
    if not include_archived:
        query = query.filter(IEPGoal.archived_at.is_(None))
    goal = query.first()
    if goal is None:
        raise ValueError(
            f"No goal with id {goal_id}. Call list_goals for the ids that exist."
        )
    _require_student(ctx, goal.student_id, f"goal {goal_id}")
    return goal


def _load_objective(
    db: Session, ctx: McpPrincipal, objective_id: int, include_archived: bool = False
) -> GoalObjective:
    query = db.query(GoalObjective).filter(GoalObjective.id == objective_id)
    if not include_archived:
        query = query.filter(GoalObjective.archived_at.is_(None))
    objective = query.first()
    if objective is None:
        raise ValueError(
            f"No objective with id {objective_id}. Call list_objectives for a "
            f"goal to see the ids that exist."
        )
    _require_student(ctx, objective.goal.student_id, f"objective {objective_id}")
    return objective


def _load_entry(
    db: Session, ctx: McpPrincipal, entry_id: int, include_archived: bool = False
) -> ObjectiveProgressEntry:
    query = db.query(ObjectiveProgressEntry).filter(
        ObjectiveProgressEntry.id == entry_id
    )
    if not include_archived:
        query = query.filter(ObjectiveProgressEntry.archived_at.is_(None))
    entry = query.first()
    if entry is None:
        raise ValueError(
            f"No progress entry with id {entry_id}. Call list_progress_entries "
            f"for an objective to see the ids that exist."
        )
    _require_student(ctx, entry.objective.goal.student_id, f"progress entry {entry_id}")
    return entry


def _load_session(
    db: Session, ctx: McpPrincipal, session_id: int, include_archived: bool = False
) -> TherapySession:
    query = db.query(TherapySession).filter(TherapySession.id == session_id)
    if not include_archived:
        query = query.filter(TherapySession.archived_at.is_(None))
    row = query.first()
    if row is None:
        raise ValueError(
            f"No therapy session with id {session_id}. Call "
            f"list_therapy_sessions for the ids that exist."
        )
    _require_student(ctx, row.student_id, f"therapy session {session_id}")
    return row


def _archive_refusal(what: str, summary: dict) -> dict:
    """The confirm=false answer, for every archive_* tool.

    Same shape the old delete tools used, and deliberately so -- a client that
    knew how to show `wouldDelete` gets `wouldArchive` in the same place. The
    difference is in the wording, because the decision being confirmed is a
    different one: this hides a record, it does not end it.
    """
    return {
        "archived": False,
        "reason": f"confirm must be true to archive {what}",
        "wouldArchive": summary,
        "note": (
            "Archiving hides these records from working lists. Nothing is "
            "deleted, every field is kept, and one call to restore_archived "
            "puts all of it back."
        ),
    }


def _student_alias_for(db: Session, student_id: Optional[int]) -> Optional[str]:
    """`student_12` for an id, without loading the whole record."""
    if student_id is None:
        return None
    row = db.query(Student).filter(Student.id == student_id).first()
    return row.alias if row else None


def _do_archive(
    db: Session,
    ctx: McpPrincipal,
    entity_type: str,
    entity_id: int,
    reason: Optional[str],
    summary: dict,
) -> dict:
    """The confirmed half of every archive_* tool.

    One place, so the answer shape and the "already archived" refusal cannot
    drift between six tools.
    """
    try:
        event = archive_service.archive(
            db,
            user_id=ctx.user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
        )
    except archive_service.AlreadyArchivedError as exc:
        raise ValueError(
            f"{exc} Call list_archive_events to find it, or restore_archived "
            f"to bring it back."
        ) from None
    return {
        "archived": True,
        "archiveEventId": event.id,
        "hidden": summary,
        "contents": archive_service.event_contents(db, event.id),
        "note": (
            "Nothing was deleted. Call restore_archived("
            f"event_id={event.id}, confirm=true) to put all of it back."
        ),
    }


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
            db.query(IEPGoal)
            .filter(IEPGoal.student_id.in_(ids), IEPGoal.archived_at.is_(None))
            .all()
            if ids
            else []
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
            .filter(ObjectiveProgressEntry.archived_at.is_(None))
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
        # `include_archived=False` on purpose. The repository default is True
        # because the React student page is where a therapist unarchives, and
        # hiding the row there would take the button away. This connection has
        # no such page: an agent that can read an archived student's whole
        # record by id would be quoting a retired record as a live one.
        # list_archive_events is where an archived student is visible here.
        student = StudentRepository(db).get_student_by_id(
            student_id, include_archived=False
        )
        if student is None:
            raise ValueError(
                f"No student with id {student_id}. Call list_students for the "
                f"ids that exist, or list_archive_events if you think this one "
                f"was archived."
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

    Only ACTIVE goals come back. Archived goals are hidden here by design --
    list_archive_events is where they are, and restore_archived brings one back.

    Omit `student_id` to sweep the whole caseload. Each row's `id` is the
    `goal_id` for get_goal, list_objectives, update_goal and archive_goal.
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
                        # The join row is never archived; the student can be.
                        and assignment.student.archived_at is None
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
    use archive_progress_entry, which hides it (recoverably) and refuses
    without confirm=true.
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
# archive tools — recoverable by design, and all refuse without confirm=true
# --------------------------------------------------------------------------
# There are no delete tools here any more. `archive_*` stamps a record and
# everything under it with one archive event and hides it from working lists;
# `list_archive_events` shows those events and `restore_archived` reverses one.
# Every field of every archived row is still in the database.
#
# The confirm=true gate is KEPT even though nothing is destroyed. It is not
# there to protect the data (the restore does that) -- it is there so that a
# therapist finds out her caseload is about to lose a goal from a summary she
# was shown, rather than from the goal being gone. The refusal branch returns
# the counts of what would be hidden, exactly as the old delete tools did.
@tool()
def archive_progress_entry(
    entry_id: int, confirm: bool = False, reason: Optional[str] = None
) -> dict:
    """
    WRITE — archives one progress entry. RECOVERABLE; nothing is destroyed.

    The observation, its date, its notes and its attribution are all kept. The
    entry stops appearing in list_progress_entries and stops counting towards
    the objective's progress, and that is the whole of the change. The call
    returns an `archiveEventId`; restore_archived(that id, confirm=true) puts
    the entry back exactly as it was.

    `confirm` must be literally true. Anything else — false, "yes", omitted —
    archives nothing and returns a summary of what WOULD be hidden, so a record
    can never vanish from a caseload because a tool call was half-formed. Show
    that summary to a human and get an answer before you send confirm=true.

    `entry_id` comes from list_progress_entries. To fix a wrong value, prefer
    update_progress_entry — archiving is for an entry that should not have been
    logged at all.
    """
    db = _session()
    try:
        ctx = _ctx()
        entry = _load_entry(db, ctx, entry_id, include_archived=True)
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
            "student": _student_alias_for(db, goal.student_id),
            "willArchive": archive_service.preview(
                db, archive_service.ENTITY_PROGRESS_ENTRY, entry_id
            ),
        }
        if confirm is not True:
            return _archive_refusal("this progress entry", summary)
        return _do_archive(
            db, ctx, archive_service.ENTITY_PROGRESS_ENTRY, entry_id, reason, summary
        )
    finally:
        db.close()


@tool()
def archive_objective(
    objective_id: int, confirm: bool = False, reason: Optional[str] = None
) -> dict:
    """
    WRITE — archives one objective AND the progress entries under it.
    RECOVERABLE; nothing is destroyed.

    The objective stops appearing under its goal and its entries stop appearing
    in list_progress_entries. Every row is kept, and one call to
    restore_archived with the returned `archiveEventId` brings the whole set
    back together.

    `confirm` must be literally true. Without it this archives nothing and
    instead returns the count of entries that would be hidden — show that to a
    human and get an answer before sending confirm=true.

    `objective_id` comes from list_objectives. If the objective is simply
    finished, update_objective with a progress_status is usually what you want:
    it keeps the objective visible as completed work.
    """
    db = _session()
    try:
        ctx = _ctx()
        objective = _load_objective(db, ctx, objective_id, include_archived=True)
        goal = objective.goal
        summary = {
            "objectiveId": objective.id,
            "objectiveNumber": objective.objective_number,
            "objectiveDescription": objective.objective_description,
            "goalId": goal.id,
            "studentId": goal.student_id,
            "student": _student_alias_for(db, goal.student_id),
            "willArchive": archive_service.preview(
                db, archive_service.ENTITY_OBJECTIVE, objective_id
            ),
        }
        if confirm is not True:
            return _archive_refusal("this objective and its progress entries", summary)
        return _do_archive(
            db, ctx, archive_service.ENTITY_OBJECTIVE, objective_id, reason, summary
        )
    finally:
        db.close()


@tool()
def archive_goal(goal_id: int, confirm: bool = False, reason: Optional[str] = None) -> dict:
    """
    WRITE — archives an IEP goal AND EVERYTHING UNDER IT: every objective, and
    every progress entry logged against those objectives. RECOVERABLE; nothing
    is destroyed.

    This is the widest-reaching archive on a single goal, and the history it
    hides is the evidence a school has that services were delivered — so say
    what is about to disappear from the caseload before you do it. But it does
    not disappear from the DATABASE: every row keeps every field, and
    restore_archived with the returned `archiveEventId` brings the whole tree
    back.

    In most cases the thing you actually want is update_goal with
    goal_status="Mastered" or "Discontinued", which keeps the goal visible as
    finished work. Archive is for a goal that should not be on the caseload at
    all.

    An objective already archived under an EARLIER event keeps that event and is
    not swept into this one, so restoring this event will not resurrect work
    that was retired on purpose.

    `confirm` must be literally true. Without it this archives nothing and
    returns a count of the objectives and entries that would be hidden.

    `goal_id` comes from list_goals.
    """
    db = _session()
    try:
        ctx = _ctx()
        goal = _load_goal(db, ctx, goal_id, include_archived=True)
        objectives = list(goal.objectives or [])
        summary = {
            "goalId": goal.id,
            "studentId": goal.student_id,
            "student": _student_alias_for(db, goal.student_id),
            "goalNumber": goal.goal_number,
            "goalDescription": goal.goal_description,
            "goalStatus": goal.goal_status,
            "objectives": len(objectives),
            "progressEntries": sum(len(o.progress_entries or []) for o in objectives),
            "objectiveNumbers": sorted(o.objective_number for o in objectives),
            "willArchive": archive_service.preview(
                db, archive_service.ENTITY_GOAL, goal_id
            ),
        }
        if confirm is not True:
            return _archive_refusal("this goal and everything under it", summary)
        return _do_archive(db, ctx, archive_service.ENTITY_GOAL, goal_id, reason, summary)
    finally:
        db.close()


@tool()
def archive_therapy_session(
    session_id: int, confirm: bool = False, reason: Optional[str] = None
) -> dict:
    """
    WRITE — archives one therapy session. RECOVERABLE; nothing is destroyed.

    The session, its notes, its planned goals and objectives stop appearing in
    list_therapy_sessions and stop counting towards session statistics.

    The PROGRESS ENTRIES logged during the session are deliberately left active.
    They belong to an objective, not to the session, and they are the record
    that a service was delivered — hiding a session must not blank a child's
    data. If you mean to hide an entry too, archive_progress_entry does that
    one at a time.

    `confirm` must be literally true. Without it nothing is archived and a
    summary comes back instead. `session_id` comes from list_therapy_sessions.
    """
    db = _session()
    try:
        ctx = _ctx()
        row = _load_session(db, ctx, session_id, include_archived=True)
        summary = {
            "sessionId": row.id,
            "studentId": row.student_id,
            "student": _student_alias_for(db, row.student_id),
            "sessionDate": row.session_date.isoformat() if row.session_date else None,
            "status": row.status,
            "sessionType": row.session_type,
            "appointmentId": row.appointment_id,
            "progressEntriesLeftActive": len(row.progress_entries or []),
            "willArchive": archive_service.preview(
                db, archive_service.ENTITY_THERAPY_SESSION, session_id
            ),
        }
        if confirm is not True:
            return _archive_refusal("this therapy session", summary)
        return _do_archive(
            db, ctx, archive_service.ENTITY_THERAPY_SESSION, session_id, reason, summary
        )
    finally:
        db.close()


@tool()
def archive_student(
    student_id: int, confirm: bool = False, reason: Optional[str] = None
) -> dict:
    """
    WRITE — THE WIDEST-REACHING TOOL HERE. Archives a student AND their whole
    record: every IEP goal, every objective, every progress entry, every therapy
    session and every appointment. RECOVERABLE; nothing is destroyed.

    This is what you use when a child leaves the caseload. Their record stops
    appearing anywhere — list_students, list_goals, the schedule, the statistics
    — and stays complete in the database. restore_archived with the returned
    `archiveEventId` brings the entire record back at once.

    Anything already archived under an EARLIER event keeps that event: restoring
    this one returns the student to the caseload without undoing a goal that was
    retired months ago.

    `confirm` must be literally true. Without it this archives nothing and
    returns the counts — goals, objectives, entries, sessions, appointments —
    that would be hidden. That count is what you show a human. This is a large
    change to a caseload and should never be the first thing you do in a
    conversation.

    `student_id` comes from list_students. The student is identified by alias
    ("student_12") in everything this tool returns.
    """
    db = _session()
    try:
        ctx = _ctx()
        _require_student(ctx, student_id, "archiving this student")
        student = db.query(Student).filter(Student.id == student_id).first()
        if student is None:
            raise ValueError(
                f"No student with id {student_id}. Call list_students for the "
                f"ids that exist."
            )
        summary = {
            "studentId": student.id,
            "student": student.alias,
            "enrollmentStatus": student.enrollment_status,
            "gradeLevel": student.grade_level,
            "willArchive": archive_service.preview(
                db, archive_service.ENTITY_STUDENT, student_id
            ),
        }
        if confirm is not True:
            return _archive_refusal("this student and their whole record", summary)
        return _do_archive(
            db, ctx, archive_service.ENTITY_STUDENT, student_id, reason, summary
        )
    finally:
        db.close()


@tool()
def list_archive_events(
    include_restored: bool = False,
    root_entity_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Everything that has been archived on this caseload, newest first — the
    undo history.

    One row per archive action: what was archived (`rootEntityType` +
    `rootEntityId`), when, why (if a reason was given), how many rows of each
    kind it still holds (`contents`), and whether it has already been restored.
    Students appear as aliases ("student_12"), never as names.

    `eventId` is what restore_archived wants. `include_restored=false` (the
    default) shows only archives that are still in force, which is what you want
    when somebody asks "what did I hide?". `root_entity_type` narrows to one
    kind: student, goal, objective, progress_entry, therapy_session,
    appointment, time_block.

    An ADMIN sees every user's events, because restore_archived lets an admin
    restore every user's events; `ownedByCaller` says which are their own. A
    therapist sees only their own, and `ownedByCaller` is true on all of them.

    Use this before restore_archived, always: it is how you find the event id
    and how you tell a human what putting it back would bring with it.
    """
    db = _session()
    try:
        ctx = _ctx()
        if root_entity_type is not None and root_entity_type not in ARCHIVABLE_ENTITY_TYPES:
            raise ValueError(
                f"Unknown entity type '{root_entity_type}'. Expected one of: "
                f"{', '.join(sorted(ARCHIVABLE_ENTITY_TYPES))}."
            )
        # `None` means every user's events. It is what an admin gets, and it
        # has to be, because `restore_archived` already lets an admin restore
        # an event they do not own: listing scoped to self would leave them
        # able to restore only by GUESSING an id -- a blind write against a
        # record they were never shown. The caseload check below still applies
        # to every row, admin or not.
        events = archive_service.list_events(
            db,
            user_id=None if ctx.is_admin else ctx.user_id,
            include_restored=include_restored,
            root_entity_type=root_entity_type,
            limit=max(1, min(int(limit), 200)),
        )
        rows = []
        for event in events:
            payload = archive_service.event_summary(db, event)
            payload["ownedByCaller"] = event.user_id == ctx.user_id
            # Every event is scoped to a student where one exists, and it is
            # named by ALIAS -- the same identity every other tool uses.
            try:
                student_id = archive_service.root_student_id(
                    db, event.root_entity_type, event.root_entity_id
                )
            except archive_service.ArchiveError:
                student_id = None
            if student_id is not None and not ctx.may_see_student(student_id):
                continue
            payload["student"] = _student_alias_for(db, student_id)
            payload["studentId"] = student_id
            rows.append(payload)
        return rows
    finally:
        db.close()


@tool()
def restore_archived(event_id: int, confirm: bool = False) -> dict:
    """
    WRITE — puts one archive event's records back on the caseload. This is the
    undo for every archive_* tool.

    It restores EXACTLY the rows that event archived and nothing else. Anything
    that was already archived when the event ran kept its own older event and
    stays archived — so restoring a student does not resurrect a goal that was
    retired before she left.

    Restoring a record whose PARENT is still archived is refused: putting a goal
    back under a hidden student would leave a row nothing can reach. The refusal
    names the parent's event so you know which one to restore first.

    `confirm` must be literally true — this changes what appears on a working
    caseload, and the therapist should be the one deciding that a record comes
    back. Without it nothing is restored and a summary of what would return
    comes back instead.

    `event_id` comes from list_archive_events.
    """
    db = _session()
    try:
        ctx = _ctx()
        try:
            event = archive_service.get_event(db, event_id)
        except archive_service.EntityNotFoundError as exc:
            raise ValueError(str(exc)) from None

        if event.user_id != ctx.user_id and not ctx.is_admin:
            raise ValueError(
                f"Archive event {event_id} does not belong to you. Call "
                f"list_archive_events for the events you can restore."
            )
        student_id = archive_service.root_student_id(
            db, event.root_entity_type, event.root_entity_id
        )
        if student_id is not None:
            _require_student(ctx, student_id, f"archive event {event_id}")

        summary = archive_service.event_summary(db, event)
        summary["student"] = _student_alias_for(db, student_id)
        summary["studentId"] = student_id

        if confirm is not True:
            return {
                "restored": False,
                "reason": "confirm must be true to restore this archive event",
                "wouldRestore": summary,
            }

        try:
            result = archive_service.restore(db, user_id=ctx.user_id, event_id=event_id)
        except archive_service.AlreadyRestoredError as exc:
            raise ValueError(str(exc)) from None
        except archive_service.ParentStillArchivedError as exc:
            raise ValueError(str(exc)) from None

        result["student"] = _student_alias_for(db, student_id)
        result["note"] = (
            "Only the rows this event archived came back. Anything archived "
            "under a different event is still archived -- call "
            "list_archive_events to see what is left."
        )
        return result
    finally:
        db.close()


# --------------------------------------------------------------------------
# staged caseload import
# --------------------------------------------------------------------------
# Six tools around one idea: the spreadsheet enters the server through the
# therapist's own browser, and what crosses this connection is its STRUCTURE.
# See app/services/blind_import.py for the whole argument; the tools here are
# thin, because everything they do has to be identical to what the upload route
# does and neither may be the authority.


def _import_batch(db: Session, ctx: McpPrincipal, batch_id: int) -> ImportBatch:
    """The caller's own batch, or a refusal. No admin override -- see get_batch."""
    return blind_import.get_batch(db, batch_id, ctx.user_id)


@tool()
def create_import_upload() -> dict:
    """
    START HERE to import a caseload from a spreadsheet of ANY layout. Creates an
    empty import batch and returns a one-shot upload link for the therapist to
    open in her own browser.

    Give her the `uploadUrl` and ask her to upload the file there. DO NOT ask
    her to paste the spreadsheet, its rows, or a sample of it into this
    conversation -- that would put children's names, birthdays and state
    identifiers into a chat transcript, which is the exact thing this whole
    mechanism exists to avoid. If she pastes one anyway, say so, do not work
    with it, and offer this link instead.

    The link works ONCE and expires in 30 minutes. Nothing has been imported
    when it comes back; the file is only staged.

    Then: get_import_preview -> set_import_mapping -> validate_import ->
    commit_import -> discard_import.
    """
    db = _session()
    try:
        ctx = _ctx()
        batch, secret = blind_import.create_batch(db, ctx.user_id)
        origin = settings.public_origin.rstrip("/")
        return {
            "batchId": batch.id,
            "uploadUrl": f"{origin}/import/upload/{secret}",
            "expiresInMinutes": int(
                blind_import.UPLOAD_TOKEN_TTL.total_seconds() // 60
            ),
            "singleUse": True,
            "accepts": [".xlsx", ".csv"],
            "maxRows": blind_import.MAX_DATA_ROWS,
            "maxMegabytes": blind_import.MAX_UPLOAD_BYTES // (1024 * 1024),
            "nextStep": (
                "Ask the therapist to open this link and upload the file, then "
                "call get_import_preview with this batchId. Do not ask for the "
                "spreadsheet's contents in chat."
            ),
        }
    finally:
        db.close()


@tool()
def get_import_preview(batch_id: int) -> dict:
    """
    What the uploaded file LOOKS like, with none of it quoted.

    Every cell comes back as a SHAPE, not a value: letters become X or x with
    the case preserved, digits become #, and punctuation and spacing survive.
    So a surname column reads "Xxxxxxx", a birthday column reads "##/##/####",
    and a "Last, First" column reads "Xxxxxxx, Xxxxx" -- which is everything you
    need to work out what a column is, and nothing about any child.

    Per sheet you get: its dimensions, the rows that look like header rows (with
    their header TEXT, which is the one thing shown verbatim, because column
    names are what a mapping is made of), and per column a summary of
    non-empty count, distinct-value COUNT and the three commonest shapes.

    A sheet with no detectable header row reports its columns by letter with no
    header text at all. That is deliberate: row 1 of a header-less caseload
    export is a child, not a heading. It also happens to sheets that DO have a
    header when the heading is the same shape as the column under it ("First"
    over "Anna"), because nothing can tell those apart -- ask the therapist what
    the columns are and map them by letter.

    Read the shapes, propose a mapping to the therapist in plain language
    ("column C looks like dates -- is that the IEP date or the annual review?"),
    and then call set_import_mapping.
    """
    db = _session()
    try:
        ctx = _ctx()
        return blind_import.preview(db, _import_batch(db, ctx, batch_id))
    finally:
        db.close()


@tool()
def set_import_mapping(batch_id: int, mapping: dict) -> dict:
    """
    Record what each column means, and unlock the columns that are safe to read.

    `mapping` is an object:

      sheet             the sheet name from get_import_preview
      header_row        1-based row number of the headings (optional)
      data_start_row    1-based row the students start on (defaults to
                        header_row + 1)
      columns           {"A": "last_name", "B": "first_name", "C": "ignore", ...}
      value_overrides   optional, see below

    Field names: first_name, last_name, full_name_last_first,
    full_name_first_last, date_of_birth, uic, school, teacher, case_manager,
    grade_level, enrollment_status, iep_date, annual_review_due_date,
    reevaluation_due_date, eligibility, notes, ignore.

    Name the student EITHER as first_name + last_name OR as one full_name_*
    column. Mapping a column to "ignore" is a real answer and better than
    leaving it out.

    WHAT COMES BACK: the stored mapping plus, for the first time, real sample
    values -- but only from columns mapped to school, teacher, case_manager,
    grade_level, enrollment_status, iep_date, annual_review_due_date,
    reevaluation_due_date or eligibility. Those name a building, an adult, a
    grade or a compliance date. Columns mapped to a name, a date of birth, a
    UIC or notes stay masked forever; asking again will not change that.

    The value has to LOOK like the field as well: a cell that is a date, a long
    identifier or a paragraph is not shown even from a column mapped to
    `school`, and `valuesNotShowable` counts how many were held back. A count
    above zero means the mapping is wrong, not that the tool is being coy.

    `value_overrides` is how you fix an unknown school or teacher after
    validate_import reports one:

      {"school": {"Nrthgate El": "Northgate Elementary"}}

    Call list_schools and list_teachers to get the existing spellings. This
    import NEVER creates a school or a teacher -- a fuzzy match is a suggestion,
    not a licence to add a second Northgate Elementary.

    Re-call this as often as you need; it replaces the whole mapping.
    """
    db = _session()
    try:
        ctx = _ctx()
        batch = _import_batch(db, ctx, batch_id)
        return blind_import.set_mapping(db, batch, mapping, _alias_contexts())
    finally:
        db.close()


@tool()
def validate_import(batch_id: int) -> dict:
    """
    Check every row against the mapping and report the problems BY ROW NUMBER.

    What you get is a row number, a column letter and a kind of problem. You do
    NOT get the value that caused it, unless that value is one this server is
    allowed to show you:

      unparseable_date        row + column + the value's SHAPE
      missing_required        row + which field is missing
      value_too_long          row + column + the length, never the text
      duplicate_uic_in_file   the PAIR of row numbers, never the identifier
      duplicate_uic_existing  row + the existing student's ALIAS
      unknown_school          row + column. The VALUE is said once, in
      unknown_teacher         `unresolvedValues`, not once per student.
      unknown_case_manager
      unknown_eligibility     row + column (warning only), grouped the same way

    BLOCKING: missing names, over-long values, unknown school / teacher /
    case_manager, and both duplicate-UIC kinds. Everything else is a warning --
    an unparseable date is simply left empty on the student.

    Resolve unknown schools and teachers with `value_overrides` in
    set_import_mapping, then call this again. `unresolvedValues` groups them for
    you: one entry per distinct spelling, with the rows it appears on, capped in
    length (`unresolvedValuesTruncated` counts what is past the cap).

    An entry that reports `valueShape` instead of `value` is a cell that does
    not look like a building, an adult or a category -- a birthday or an
    identifier, say. That means the column is mapped to the wrong field. Fix the
    mapping; asking again will not print it.

    Report the counts to the therapist in plain language. She is the one who
    knows whether "Bldg 4" is Northgate.
    """
    db = _session()
    try:
        ctx = _ctx()
        return blind_import.validate(db, _import_batch(db, ctx, batch_id))
    finally:
        db.close()


@tool()
def commit_import(batch_id: int, confirm: bool = False) -> dict:
    """
    WRITE. Creates the students, all of them or none of them, and puts them on
    the calling therapist's caseload.

    The real names, dates of birth and identifiers are read from the staged file
    on the server. They are not passed in and they are not returned: what comes
    back is a count and a list of ALIASES (student_41, student_42...), which is
    the identity every other tool here uses. If the therapist wants to see who
    is who, she looks in the SLP Pro app.

    `confirm` must be literally true. Without it nothing is written and you get
    a summary of what would be -- how many students, from which rows, which
    fields will be filled. Show that to the therapist and get an answer before
    sending confirm=true.

    Refuses outright while validate_import reports blocking issues, and
    re-validates before writing regardless of what the batch's status says.

    All-or-nothing: if any row fails, every student this call created is removed
    again before the error comes back.

    Not written even when mapped: `notes` and `eligibility`. Everything else on
    the field list is.
    """
    db = _session()
    try:
        ctx = _ctx()
        batch = _import_batch(db, ctx, batch_id)
        return blind_import.commit(db, batch, ctx.user_id, confirm)
    finally:
        db.close()


@tool()
def discard_import(batch_id: int, confirm: bool = False) -> dict:
    """
    WRITE - DESTRUCTIVE, AND DESTRUCTION IS THE POINT. Deletes the import batch
    and every staged row of the uploaded spreadsheet.

    THE ONLY IRREVERSIBLE TOOL ON THIS SERVER, and the only one with no archive
    behind it -- because here the destruction is a privacy feature rather than a
    data-management one. Every other tool that hides a record (archive_student,
    archive_goal, and the rest) keeps every field and can be undone with
    restore_archived. This one cannot, on purpose.

    Those rows are the only verbatim copy of the therapist's roster export on
    this server -- real names, real birthdays, real identifiers, sitting in a
    table nothing else reads. Discarding is how she gets rid of it the moment
    the import is done, rather than waiting for a retention policy. OFFER THIS
    after a successful commit_import.

    Students already created by commit_import are NOT touched. They are ordinary
    caseload records now and this does not reach them.

    `confirm` must be literally true. Without it nothing is deleted and you get
    a count of what would go.
    """
    db = _session()
    try:
        ctx = _ctx()
        batch = _import_batch(db, ctx, batch_id)
        return blind_import.discard(db, batch, confirm)
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
