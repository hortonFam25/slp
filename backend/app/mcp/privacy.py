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
   first, last and full name — in every spelling a note plausibly uses, accents
   folded and compounds split — and of every student's date of birth and UIC in
   the formats those get typed in. This catches the thing structure cannot: an
   identifier composed into a sentence, in a progress comment, a session note,
   an objective description, or an error message. A DOB written into a note is
   the same DOB as the one in the column the structural layer removed.

Both run on every tool result and every tool error. Neither is optional and
neither is per-tool — see `app.mcp.server.tool`, the decorator that applies
them.

Everything here is deterministic and offline: same input, same output, no
network, no model.
"""

from __future__ import annotations

import dataclasses
import functools
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence

from sqlalchemy.orm import Session

from app.ai.privacy import StudentAliasContext, build_student_alias
from app.models.student import Student

# ---------------------------------------------------------------------------
# policy constants
# ---------------------------------------------------------------------------
# Flip to True to extend the STRUCTURAL strip to teachers, case managers,
# school contacts and principals. It is False in v1 on purpose: a teacher's
# name is ORGANISATIONAL context (which adult owns this IEP, which classroom,
# which building), not student PII, and stripping it would make the schedule
# and the case-manager fields useless to an agent without protecting a student.
#
# Read what this flag does NOT do before relying on it: it adds keys to the
# deny list and nothing more. The free-text scrubber redacts against a roster
# of STUDENTS (`build_contexts`), so a teacher named in a session note is
# untouched whichever way this is set. Redacting staff from prose is a second
# change — a staff roster alongside the student one — not a flip of this
# constant.
REDACT_STAFF_NAMES = False

# A name shorter than this is not redacted from free text. Two characters of
# alternation would turn every "Al…" and "An…" in a clinical note into an
# alias; the protection is not worth the shredding, and a one-character name is
# not a name. Raise it if a caseload ever contains a name that is also a common
# word.
MIN_REDACTABLE_NAME_LENGTH = 2

# A name PART derived by splitting a compound name ("Garcia-Lopez" -> "Garcia",
# "Lopez") is held to a stricter floor than the name itself. The parts are
# guesses about how a clinician might abbreviate in prose, so the cost of a
# false positive is borne by text nobody asked to have redacted; "Al-Sayed"
# must not turn every "Al" in the caseload's notes into an alias.
MIN_REDACTABLE_NAME_PART_LENGTH = 3

# An identifier (UIC) shorter than this is not scrubbed from free text. A
# three-character identifier is indistinguishable from a trial count or an
# initialism, and shredding those would cost more than the identifier is worth.
MIN_REDACTABLE_IDENTIFIER_LENGTH = 4

# What a scrubbed direct identifier becomes. Deliberately NOT the alias: an
# alias is an identity, and "born [redacted]" says the right thing where "born
# student_12" would read as a second student.
IDENTIFIER_PLACEHOLDER = "[redacted]"

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
        # Other spellings of the STUDENT's own name. None of these is on a
        # model today; they are here so that the day one is added it is aliased
        # on the deploy that adds it, not on the deploy that notices.
        "childname",
        "legalname",
        "preferredname",
        "nickname",
        "middlename",
        "maidenname",
        "formername",
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
        # A guardian, a parent or an emergency contact is a DIFFERENT person
        # from the student, so there is no alias to rewrite them to — the alias
        # scheme names students. Aliasing them would say "the guardian is
        # student_12", which is worse than saying nothing. Dropped outright.
        "parent",
        "parentname",
        "guardian",
        "guardianname",
        "parentguardian",
        "parentguardianname",
        "emergencycontact",
        "emergencycontactname",
        # Contact details. No tool here sends mail, dials a number or plots an
        # address, so nothing downstream needs one — and a direct line to a
        # child's teacher is exactly the sort of thing that should not be
        # sitting in a model vendor's transcript store. This costs the agent
        # nothing and is the cheapest square metre of the whole filter.
        "email",
        "emailaddress",
        "personalemail",
        "phone",
        "phonenumber",
        "telephone",
        "mobile",
        "mobilephone",
        "cellphone",
        "homephone",
        "workphone",
        "address",
        "streetaddress",
        "homeaddress",
        "mailingaddress",
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

# What separates the parts of a compound name: hyphens (ASCII and the Unicode
# dash block), straight and curly apostrophes, and whitespace.
_NAME_PART_SPLIT = re.compile(r"[-‐-―'‘’\s]+")

# One word of running text. An apostrophe is INSIDE the token only when it sits
# between two word characters, so "O'Brien" is looked up whole while the
# quotation mark closing `(got 'Vandergriff')` is not dragged in — a trailing
# quote turns a name into a token nothing matches, which is a leak wearing
# punctuation. Hyphens are OUTSIDE the token so "pre-Braddock" is looked up as
# two words and the name half is still found. Nothing here depends on the
# caseload, so it compiles once for the process.
_WORD = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)

# Apostrophes, kept as split groups so a possessive can be rebuilt: "Jane's"
# has to come back as "student_7's", not be left alone because the token with
# its "'s" attached matched nothing.
_APOSTROPHE_SPLIT = re.compile(r"(['’])")

# Leaf values the recursion hands back as they are: they have no fields to
# strip and their rendering is a number or a timestamp, not text anybody wrote.
# Everything NOT on this list is stringified and scrubbed — see `_sanitize`.
_SCALARS = (str, bool, int, float, complex, bytes, date, datetime, Decimal, Enum)

# Anything date-SHAPED. This does not decide what is a birthday — the roster's
# rendering set does that, in `_Scrubber._redact_date`. Its only job is to find
# the candidates in one pass, so the work is proportional to the length of the
# text and not to the number of students on the caseload.
_MONTHS = (
    "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
    "|january|february|march|april|june|july|august"
    "|september|october|november|december"
)
_DATE_SHAPES = re.compile(
    r"""
      \b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b            # 2011-03-17, 2011/03/17
    | \b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b          # 3/17/2011, 03-17-11
    | \b(?:MONTHS)\.?\s+\d{1,2},?\s+\d{4}\b        # March 17, 2011
    | \b\d{1,2}\s+(?:MONTHS)\.?,?\s+\d{4}\b        # 17 March 2011
    """.replace("MONTHS", _MONTHS),
    re.IGNORECASE | re.VERBOSE,
)

# Runs of whitespace inside a matched date, so "March  17,  2011" compares
# equal to the rendering the roster generated.
_NORMALIZE_SPACES = re.compile(r"\s+")

# "student_7 student_7" -> "student_7". Tokenising means a note that wrote a
# full name produces the alias twice, once per word; this puts the sentence
# back together. Hyphens are included so "Garcia-Lopez" does not come back as
# "student_7-student_7".
_ADJACENT_ALIAS = re.compile(r"\b(student_\d+)(?:[\s\-]+\1)+\b", re.IGNORECASE)


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
@dataclasses.dataclass(frozen=True)
class McpStudentContext(StudentAliasContext):
    """
    A student's alias context PLUS the two direct identifiers.

    A subclass rather than a widening of `StudentAliasContext` because that
    type is the app's, shared with the in-app AI chat, and the AI chat has no
    business carrying a DOB around. Everything that consumes a context here
    reads the extra fields with `getattr(..., None)`, so a plain
    `StudentAliasContext` — what the sanitizer's own unit tests hand it — still
    works and simply scrubs names only.
    """

    date_of_birth: Optional[date] = None
    uic: Optional[str] = None


def build_contexts(db: Session, principal: Any = None) -> tuple[StudentAliasContext, ...]:
    """
    One `McpStudentContext` per student, built once per tool call.

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

    One indexed read of six columns, on every call, uncached: a cached roster
    is a roster that can be stale, and a stale roster is a name that does not
    get redacted. (`_scrubber_for` caches the LOOKUP built from a roster, keyed
    by that roster's own contents — which is a different thing and cannot go
    stale, because a changed roster is a different key.)
    """
    rows = (
        db.query(
            Student.id,
            Student.first,
            Student.last,
            Student.student_alias,
            Student.date_of_birth,
            Student.uic,
        )
        .order_by(Student.id)
        .all()
    )
    return tuple(
        McpStudentContext(
            student_id=row.id,
            alias=row.student_alias or build_student_alias(row.id),
            first_name=row.first or "",
            last_name=row.last or "",
            date_of_birth=row.date_of_birth,
            uic=(row.uic or "").strip() or None,
        )
        for row in rows
    )


# ---------------------------------------------------------------------------
# free-text scrubbing
# ---------------------------------------------------------------------------
def _name_variants(token: str) -> set[str]:
    """
    Every spelling of one name a note might plausibly use.

    Three problems, one function:

    * **Composition.** "José" is one code point in NFC and two in NFD, and a
      note pasted out of one system and a roster loaded from another routinely
      disagree. The matcher compares code points, so both forms go in.
    * **Accents dropped.** A clinician typing quickly writes "Jose". That is
      still the child's name and still identifies her, so the accent-folded
      form goes in too.
    * **Compounds.** A surname of "Garcia-Lopez" appears in prose as "Garcia",
      and a full name is two words that get written one at a time. Each part of
      a hyphenated, apostrophised or spaced name is added separately, at a
      stricter length floor (MIN_REDACTABLE_NAME_PART_LENGTH) because a part is
      a guess about how somebody abbreviates and a short guess shreds text.

    Everything returned is a redaction candidate, never a leak: the worst a
    spurious variant can do is alias a word that was not a name.
    """
    token = (token or "").strip()
    if not token:
        return set()

    def _forms(value: str) -> set[str]:
        nfc = unicodedata.normalize("NFC", value)
        nfd = unicodedata.normalize("NFD", value)
        folded = "".join(ch for ch in nfd if not unicodedata.combining(ch))
        return {value, nfc, nfd, folded}

    out = {form for form in _forms(token) if len(form) >= MIN_REDACTABLE_NAME_LENGTH}
    for part in _NAME_PART_SPLIT.split(token):
        if len(part) < MIN_REDACTABLE_NAME_PART_LENGTH:
            continue
        out.update(
            form for form in _forms(part) if len(form) >= MIN_REDACTABLE_NAME_PART_LENGTH
        )
    # A key with a separator in it can never be matched by the single-word scan
    # in `_Scrubber`, so it would be dead weight in the lookup. The parts above
    # are what actually catch a compound.
    return {form for form in out if not _NAME_PART_SPLIT.search(form)}


def _date_renderings(value: date) -> tuple[str, ...]:
    """
    The ways a date of birth gets typed into a clinical note.

    Not exhaustive and cannot be — a date is a value, not a string — but it
    covers ISO, both slash orders, dashes, dots, two-digit years and the long
    and abbreviated month forms an American school system produces. The
    structural layer already removes every FIELD that holds a DOB; this list is
    for the DOB somebody wrote into prose, which is the only place one can
    still be.

    These are LOOKUP keys, not alternatives in a pattern: `_DATE_SHAPES` finds
    the date-shaped substrings and this set decides which of them is a
    birthday. That is what keeps the cost proportional to the length of the
    text rather than to the size of the caseload.
    """
    day, month, year = value.day, value.month, value.year
    short_year = f"{year % 100:02d}"
    return (
        value.isoformat(),
        f"{year}/{month:02d}/{day:02d}",
        f"{month}/{day}/{year}",
        f"{month:02d}/{day:02d}/{year}",
        f"{day}/{month}/{year}",
        f"{day:02d}/{month:02d}/{year}",
        f"{month}-{day}-{year}",
        f"{month:02d}-{day:02d}-{year}",
        f"{month}.{day}.{year}",
        f"{month:02d}.{day:02d}.{year}",
        f"{month:02d}/{day:02d}/{short_year}",
        f"{month:02d}-{day:02d}-{short_year}",
        f"{value:%B} {day}, {year}",
        f"{value:%B} {day} {year}",
        f"{value:%b} {day}, {year}",
        f"{value:%b} {day} {year}",
        f"{day} {value:%B} {year}",
        f"{day} {value:%b} {year}",
    )


class _Scrubber:
    """
    Every student's names and direct identifiers, as three lookups over the text.

    The rule is the app's own (`app.ai.privacy.redact_student_name_from_value`):
    a student's name, case-insensitively, becomes that student's alias. What is
    different here is HOW the text is searched, and the difference is not
    cosmetic.

    The obvious implementation — one regex alternation of every name on the
    caseload — costs the regex engine one attempt per alternative per position
    in the text. On a caseload of five hundred, widened to the spellings a note
    actually uses, that is several thousand alternatives and it turns a tool
    call into a visibly slow tool call. A filter that makes the product slow is
    a filter somebody eventually proposes turning off, so the cost matters to
    the protection.

    So the text is TOKENISED once and each token is looked up in a dict, which
    is O(length of text) and indifferent to the size of the caseload:

      1. `_DATE_SHAPES` finds date-shaped substrings; a hit that is one of the
         roster's birthdays becomes `[redacted]`. Dates run first so a birthday
         is gone before anything else can see its digits.
      2. `_WORD` finds word tokens; a hit in the name/UIC lookup becomes that
         student's alias (a name) or `[redacted]` (a UIC).
      3. `_ADJACENT_ALIAS` collapses the "student_7 student_7" that step 2
         necessarily produces where a note wrote "Jane Doe" back down to
         "student_7", so the sentence still reads as a sentence.

    A name embedded in a hyphenated word ("pre-Braddock") is still caught,
    because the tokeniser splits on the hyphen and looks the parts up
    separately. An apostrophised name ("O'Brien") is one token, because the
    apostrophe is inside the token pattern.
    """

    __slots__ = ("_by_token", "_dob_renderings")

    def __init__(self, contexts: Iterable[StudentAliasContext]) -> None:
        by_token: dict[str, str] = {}
        dob_renderings: set[str] = set()

        for ctx in contexts:
            for token in (ctx.first_name, ctx.last_name):
                for variant in _name_variants(token):
                    # First writer wins: a token shared by two students
                    # (siblings share a surname) keeps the first alias rather
                    # than flapping between calls. Either alias is a redaction;
                    # neither is a leak.
                    by_token.setdefault(variant.lower(), ctx.alias)

            uic = (getattr(ctx, "uic", None) or "").strip()
            if len(uic) >= MIN_REDACTABLE_IDENTIFIER_LENGTH:
                # A UIC is not a name, so it must not become an identity:
                # "UIC student_7" would read as a second child. See
                # IDENTIFIER_PLACEHOLDER.
                by_token.setdefault(uic.lower(), IDENTIFIER_PLACEHOLDER)

            dob = getattr(ctx, "date_of_birth", None)
            if isinstance(dob, date):
                dob_renderings.update(
                    rendering.lower() for rendering in _date_renderings(dob)
                )

        self._by_token = by_token
        self._dob_renderings = dob_renderings

    def __bool__(self) -> bool:
        return bool(self._by_token or self._dob_renderings)

    def _redact_date(self, match: "re.Match[str]", text: str) -> str:
        """
        One date-shaped hit -> `[redacted]`, if it is a birthday and not alone.

        The "not alone" half is narrow and load-bearing. Every date this server
        emits is serialized to a string, so `{"iep_date": "2012-04-05"}` and a
        note reading "born 2012-04-05" are both just strings by the time they
        reach here. Rewriting the first would silently blank a legal compliance
        deadline on the rare day it collides with some child's birthday;
        rewriting the second is the entire point. A value that is EXACTLY a
        date and nothing else is a structured field — and a structured DOB
        field is already gone, `_ALWAYS_REMOVED_KEYS` took it before the text
        got here.
        """
        hit = match.group(0)
        normalized = _NORMALIZE_SPACES.sub(" ", hit).lower()
        if normalized not in self._dob_renderings:
            return hit
        if text.strip() == hit:
            return hit
        return IDENTIFIER_PLACEHOLDER

    def _redact_word(self, match: "re.Match[str]") -> str:
        """
        One word -> the alias it names, or the word.

        The whole token is tried first, so a name that CONTAINS an apostrophe
        ("O'Brien") is matched as the one thing it is. Only if that misses is
        the token taken apart at its apostrophes, which is what turns "Jane's"
        into "student_7's" — a possessive is the commonest way a name appears
        in a clinical note and it must not survive on a technicality.
        """
        token = match.group(0)
        hit = self._by_token.get(token.lower())
        if hit is not None:
            return hit
        if "'" not in token and "’" not in token:
            return token
        return "".join(
            part if index % 2 else self._by_token.get(part.lower(), part)
            for index, part in enumerate(_APOSTROPHE_SPLIT.split(token))
        )

    def scrub(self, text: str) -> str:
        if not text:
            return text
        if self._dob_renderings:
            text = _DATE_SHAPES.sub(lambda m: self._redact_date(m, text), text)
        if self._by_token:
            replaced = _WORD.sub(self._redact_word, text)
            if replaced != text:
                replaced = _ADJACENT_ALIAS.sub(r"\1", replaced)
            text = replaced
        return text


@functools.lru_cache(maxsize=4)
def _scrubber_for(contexts: tuple) -> _Scrubber:
    """
    The compiled lookups for one exact roster.

    This is NOT a cache of the roster — `build_contexts` still reads every name
    from the database on every single call, because a cached roster is a roster
    that can be stale and a stale roster is a name that does not get redacted.
    What is cached is the dictionary DERIVED from a roster, keyed by that
    roster's own contents. A student added, renamed or removed produces a
    different key and therefore a different lookup; there is no state here that
    can disagree with the database.
    """
    return _Scrubber(contexts)


def _scrubber(contexts: Iterable[StudentAliasContext]) -> _Scrubber:
    try:
        return _scrubber_for(tuple(contexts))
    except TypeError:  # pragma: no cover - a caller passed unhashable contexts
        return _Scrubber(contexts)


def scrub_text(text: str, contexts: Sequence[StudentAliasContext]) -> str:
    """Free-text redaction for one string. Cheap to call; builds no state."""
    if not isinstance(text, str):
        return text
    return _scrubber(contexts).scrub(text)


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


def _as_mapping(value: Any) -> Optional[dict]:
    """
    A composite object -> the plain dict the recursion knows how to strip.

    The recursion used to understand exactly `dict`, `list`, `tuple` and `str`
    and to return anything else UNTOUCHED. That default is the wrong way round
    for a PII floor: a tool that returned its Pydantic response model instead
    of calling `_dump` on it, or a dataclass, or a `set` of names, would have
    sailed past the filter with every field intact and no test would have said
    so. Every shape here is one a tool could plausibly return by accident, and
    the point is that accident cannot be a leak.

    Deliberately NOT converted: `date`, `datetime`, `Decimal`, `Enum` and the
    other leaf scalars, which have no fields to strip and whose repr is not
    text anybody wrote.
    """
    dump = getattr(value, "model_dump", None)  # pydantic v2
    if callable(dump) and not isinstance(value, type):
        try:
            dumped = dump(mode="json")
        except Exception:  # pragma: no cover - exotic model configs
            dumped = dump()
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _sanitize(value: Any, scrubber: _Scrubber) -> Any:
    if isinstance(value, str):
        return scrubber.scrub(value)
    if not isinstance(value, dict):
        mapped = _as_mapping(value)
        if mapped is not None:
            return _sanitize(mapped, scrubber)
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
    if isinstance(value, (list, tuple, set, frozenset)):
        # Sets come back as lists, sorted by their scrubbed rendering so the
        # output is stable — an unordered result that changes between two
        # identical calls is a test that passes on Tuesday.
        items = [_sanitize(item, scrubber) for item in value]
        if isinstance(value, (set, frozenset)):
            items.sort(key=lambda item: repr(item))
        return items
    if isinstance(value, _SCALARS) or value is None:
        return value
    # Everything else is an object this module does not understand. The SDK
    # will serialize it anyway — `to_json(..., fallback=str)` — so returning it
    # untouched means whatever its `__str__` says goes out unfiltered. Nothing
    # any tool returns today lands here; the point is that the day one does,
    # the default is scrubbed text rather than a hole.
    return scrubber.scrub(str(value))


def sanitize_tool_result(value: Any, contexts: Sequence[StudentAliasContext]) -> Any:
    """
    A tool's return value -> the same value with no student PII in it.

    Recursive over strings and over every composite shape a tool could return
    — dicts and mappings, lists, tuples, sets, dataclasses and Pydantic models
    — so an un-dumped response model is filtered rather than waved through.
    Leaf scalars (numbers, dates, enums) are returned as they came.
    Structural stripping and free-text scrubbing both run, in that order,
    at every depth.
    """
    return _sanitize(value, _scrubber(contexts))


def sanitize_error_message(message: str, contexts: Sequence[StudentAliasContext]) -> str:
    """
    A raised message -> the same message with no student PII in it.

    Error text is a real leak path and an easy one to forget: a message can
    compose a name ("Student Jane Doe is not on your caseload") or simply echo
    an argument the caller supplied, and it reaches the model exactly the way a
    result does.
    """
    return scrub_text(message, contexts)
