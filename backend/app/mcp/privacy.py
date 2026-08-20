"""
The PII floor under the MCP surface.

Why this exists at all
----------------------
`/mcp` is an AI-facing door. Whatever comes back through it is handed to a
model, may be quoted into a transcript, and may be retained by a vendor the
district never signed a DPA with. That is a different risk from the REST API,
where the reader is the therapist herself, sitting in front of the app that
owns the record.

So the policy here is deliberately STRICTER than `app/routers/students.py`:
there is no owner exception. `_should_mask_student_names()` in the REST layer
shows real names to the therapist who owns the caseload and masks only for
admins and impersonators. Over MCP, *every* caller is masked, including the
owner, because the caller is never really the therapist — it is a model acting
on her behalf.

What a student is, over MCP
---------------------------
A number and an alias. `student_12`. The alias scheme is not invented here: it
is the org's existing one (`app.ai.privacy.build_student_alias`, mirrored by
`Student.alias`), so an alias an agent sees over MCP is the same string the
in-app AI chat uses and the same string `hydrate_aliases_for_ui` knows how to
turn back into a name inside the app, where that is allowed.

Two layers, because one is not enough
-------------------------------------
1. **Structural.** Keys that carry student identity are dropped, or rewritten
   to the alias when the surrounding object says which student it is. This
   catches the shape of the payload.
2. **Free text.** Every string, at every depth, is scrubbed of every student's
   first, last and full name. This catches the thing structure cannot: a name
   composed into a sentence, in a progress comment, a session note, an
   objective description, or an error message.

Both run on every tool result and every tool error. Neither is optional and
neither is per-tool — see `app.mcp.server.tool`, the decorator that applies
them.

Everything here is deterministic and offline: same input, same output, no
network, no model.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.ai.privacy import StudentAliasContext, build_student_alias
from app.models.student import Student

# ---------------------------------------------------------------------------
# policy constants
# ---------------------------------------------------------------------------
# Flip to True to extend the scrub to teachers, case managers, school contacts
# and principals. It is False in v1 on purpose: a teacher's name is
# ORGANISATIONAL context (which adult owns this IEP, which classroom, which
# building), not student PII, and stripping it would make the schedule and the
# case-manager fields useless to an agent without protecting a student. This is
# the one-line change if a district's DPA says otherwise.
REDACT_STAFF_NAMES = False

# A name shorter than this is not redacted from free text. Two characters of
# alternation would turn every "Al…" and "An…" in a clinical note into an
# alias; the protection is not worth the shredding, and a one-character name is
# not a name. Raise it if a caseload ever contains a name that is also a common
# word.
MIN_REDACTABLE_NAME_LENGTH = 2

# Keys whose VALUE is a student's display name. They become the alias when the
# object they sit in identifies its student (a sibling `studentId` /
# `student_alias` / `alias`), and are dropped outright when it does not — an
# unattributable name is exactly the thing that must not go out.
_STUDENT_NAME_KEYS = frozenset(
    {
        "first",
        "last",
        "student",
        "studentname",
        "studentfirst",
        "studentlast",
        "studentfirstname",
        "studentlastname",
        "studentfullname",
        "studentdisplayname",
        "studentlabel",
    }
)

# Staff-name keys. Only joined to the deny list when REDACT_STAFF_NAMES is on.
_STAFF_NAME_KEYS = frozenset(
    {
        "firstname",
        "lastname",
        "fullname",
        "displayname",
        "teacher",
        "teachername",
        "casemanager",
        "casemanagername",
        "principalname",
        "contactperson",
    }
)

# Keys that are removed no matter what is in them. There is no aliased form of
# a date of birth or a state identifier that is worth anything to an agent, and
# both are direct identifiers under FERPA.
_ALWAYS_REMOVED_KEYS = frozenset(
    {
        "uic",
        "studentuic",
        "dateofbirth",
        "studentdateofbirth",
        "dob",
        "birthdate",
        "birthday",
        "ssn",
        "socialsecuritynumber",
    }
)

# Keys KEPT on purpose, listed here so the policy is readable in one place
# rather than inferred from the absence of an entry above: student id, alias,
# grade level, enrollment status, archived flag, every IEP date, school /
# teacher / case-manager references and their ids, goal and objective text,
# progress entries, therapy-session data. The clinical function of this server
# is exactly those fields; stripping them would leave an agent that cannot
# answer a question a therapist would actually ask.

# Where an object tells us which student it is about, most specific first.
_ALIAS_SOURCE_KEYS = ("studentalias", "alias")
_STUDENT_ID_KEYS = ("studentid",)

# A value that is ALREADY an alias survives a name key untouched.
_ALIAS_PATTERN = re.compile(r"^student_\d+$", re.IGNORECASE)

_NORMALIZE = re.compile(r"[^a-z0-9]+")


def _normalize_key(key: Any) -> str:
    """`student_id`, `studentId` and `Student ID` all normalise to the same."""
    return _NORMALIZE.sub("", str(key).lower())


def name_keys() -> frozenset[str]:
    """The name-bearing keys under the CURRENT policy."""
    if REDACT_STAFF_NAMES:
        return _STUDENT_NAME_KEYS | _STAFF_NAME_KEYS
    return _STUDENT_NAME_KEYS


def removed_keys() -> frozenset[str]:
    """The keys removed outright under the current policy."""
    return _ALWAYS_REMOVED_KEYS


# ---------------------------------------------------------------------------
# contexts
# ---------------------------------------------------------------------------
def build_contexts(db: Session, principal: Any = None) -> tuple[StudentAliasContext, ...]:
    """
    One `StudentAliasContext` per student, built once per tool call.

    Note what this deliberately does NOT do: scope itself to
    `principal.allowed_student_ids`. The caller's scope decides which students'
    RECORDS a tool may return — that is `McpPrincipal.may_see_student`, and it
    is enforced in the tools. It is the wrong question here. What this list
    decides is which names the scrubber can RECOGNISE, and the names most worth
    catching are precisely the ones belonging to students the caller may not
    see: a peer mentioned by name inside an accessible student's group-session
    note ("worked in a pair with Jane Doe") leaks a record the caller was never
    granted. Scoping the scrubber to the caller's caseload would let that
    through by construction.

    The superset is therefore intentional and is a strict superset of
    `allowed_student_ids`. `principal` is accepted so callers can pass it and
    so a future policy can narrow this without a signature change.

    One indexed read of four columns, on every call, uncached: a cached roster
    is a roster that can be stale, and a stale roster is a name that does not
    get redacted.
    """
    rows = (
        db.query(Student.id, Student.first, Student.last, Student.student_alias)
        .order_by(Student.id)
        .all()
    )
    return tuple(
        StudentAliasContext(
            student_id=row.id,
            alias=row.student_alias or build_student_alias(row.id),
            first_name=row.first or "",
            last_name=row.last or "",
        )
        for row in rows
    )


# ---------------------------------------------------------------------------
# free-text scrubbing
# ---------------------------------------------------------------------------
class _Scrubber:
    """
    Every student name, in one compiled alternation.

    Same rule as `app.ai.privacy.redact_student_name_from_value` — full name,
    then first, then last, case-insensitively, each replaced by that student's
    alias — but batched into a single pass instead of three regex passes per
    student. On a caseload of a few hundred that is the difference between a
    scrub that is free and one that shows up in a tool's latency.

    Longest token first so "Jane Doe" is consumed as a full name rather than
    being half-eaten by the "Jane" alternative, and `\\b` boundaries so a
    two-letter surname cannot rewrite the middle of an unrelated word.
    """

    __slots__ = ("_pattern", "_by_token")

    def __init__(self, contexts: Iterable[StudentAliasContext]) -> None:
        by_token: dict[str, str] = {}
        for ctx in contexts:
            for token in (ctx.full_name, ctx.first_name, ctx.last_name):
                token = (token or "").strip()
                if len(token) < MIN_REDACTABLE_NAME_LENGTH:
                    continue
                # First writer wins: full names are visited before their parts
                # for the same student, and a token shared by two students
                # (siblings share a surname) keeps the first alias rather than
                # flapping. Either alias is a redaction; neither is a leak.
                by_token.setdefault(token.lower(), ctx.alias)

        self._by_token = by_token
        if by_token:
            ordered = sorted(by_token, key=len, reverse=True)
            self._pattern: Optional[re.Pattern[str]] = re.compile(
                r"\b(?:" + "|".join(re.escape(tok) for tok in ordered) + r")\b",
                re.IGNORECASE,
            )
        else:
            self._pattern = None

    def __bool__(self) -> bool:
        return self._pattern is not None

    def scrub(self, text: str) -> str:
        if self._pattern is None or not text:
            return text
        return self._pattern.sub(
            lambda m: self._by_token.get(m.group(0).lower(), m.group(0)), text
        )


def scrub_text(text: str, contexts: Sequence[StudentAliasContext]) -> str:
    """Free-text redaction for one string. Cheap to call; builds no state."""
    if not isinstance(text, str):
        return text
    return _Scrubber(contexts).scrub(text)


# ---------------------------------------------------------------------------
# the sanitizer
# ---------------------------------------------------------------------------
def _alias_hint(payload: dict, scrubber: _Scrubber) -> Optional[str]:
    """The alias of the student THIS object is about, if it says."""
    normalized = {_normalize_key(k): v for k, v in payload.items()}
    for key in _ALIAS_SOURCE_KEYS:
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            return scrubber.scrub(value.strip())
    for key in _STUDENT_ID_KEYS:
        value = normalized.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return build_student_alias(value)
    return None


def _sanitize(value: Any, scrubber: _Scrubber) -> Any:
    if isinstance(value, str):
        return scrubber.scrub(value)
    if isinstance(value, dict):
        hint = _alias_hint(value, scrubber)
        out: dict = {}
        for key, item in value.items():
            normalized = _normalize_key(key)
            if normalized in _ALWAYS_REMOVED_KEYS:
                continue
            if normalized in name_keys():
                if item is None:
                    continue
                if isinstance(item, str) and _ALIAS_PATTERN.match(item.strip()):
                    out[key] = item
                elif hint:
                    out[key] = hint
                # No alias to put in its place: the field goes. A name we
                # cannot attribute is the worst case, not the harmless one.
                continue
            out[key] = _sanitize(item, scrubber)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, scrubber) for item in value]
    return value


def sanitize_tool_result(value: Any, contexts: Sequence[StudentAliasContext]) -> Any:
    """
    A tool's return value -> the same value with no student PII in it.

    Recursive over dicts, lists and strings; anything else is returned as it
    came. Structural stripping and free-text scrubbing both run, in that order,
    at every depth.
    """
    return _sanitize(value, _Scrubber(contexts))


def sanitize_error_message(message: str, contexts: Sequence[StudentAliasContext]) -> str:
    """
    A raised message -> the same message with no student PII in it.

    Error text is a real leak path and an easy one to forget: a message can
    compose a name ("Student Jane Doe is not on your caseload") or simply echo
    an argument the caller supplied, and it reaches the model exactly the way a
    result does.
    """
    return scrub_text(message, contexts)
