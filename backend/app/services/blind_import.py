"""
The blind staged import: a caseload spreadsheet the model never reads.

The problem
-----------
A therapist arrives with a spreadsheet. It is somebody's export from somebody's
student information system, so it has three junk rows above the header, a
"Legend" tab, merged title cells, a column called "Student" holding
"Ramirez, Sofia", another called "DOB", and a column called "Bldg" whose values
are abbreviations only that district uses. Rigid CSV import
(`app/services/csv_import_service.py`) handles exactly one of those layouts.
Working out what the OTHER layouts mean is the sort of thing a language model
is very good at.

But the file is a list of children's names, birthdays and state identifiers.
Pasting it into a chat is the single worst thing a therapist could do with it:
it lands in a transcript store belonging to a vendor the district never signed
a DPA with, and no amount of care afterwards takes it back.

The shape of the answer
-----------------------
The PII goes into the server WITHOUT passing through the model, and the model
is given the parts of the problem that do not need it.

    create_import_upload()  ->  a one-shot, 30-minute URL
    (the therapist opens it in her own browser and uploads the file;
     the server parses it and stores the rows)
    get_import_preview()    ->  SHAPES: "Xxxxxx, Xxxxx", "##/##/####", counts
    set_import_mapping()    ->  the agent says which column means what;
                                only NOW are real values revealed, and only
                                for the organisational allow-list
    validate_import()       ->  problems by ROW NUMBER, never by value
    commit_import()         ->  students created from the stored cells
    discard_import()        ->  the staged copy destroyed

At no point does a name, a date of birth or a UIC leave the server. What
crosses is structure: shapes, counts, row numbers, aliases, and the handful of
values (school, teacher, grade, compliance dates, eligibility) that name an
institution rather than a child.

Where the PII actually lives
----------------------------
`import_rows.cells_json`, and nowhere else. Nothing in this module returns it;
`app.mcp.privacy` drops the key structurally if anything ever tries; and
`backend/tests/test_blind_import.py` asserts the absence rather than trusting
it.

Deliberate limits, so they are choices rather than surprises
------------------------------------------------------------
* An unknown school or teacher is BLOCKING and is never invented. The rigid CSV
  importer creates a school it has not heard of, which is how a district ends
  up with "Northgate El", "Northgate Elem." and "Northgate Elementary" as three
  buildings. Here the agent has to reconcile the spelling against what exists,
  which it can do because school and teacher values are on the reveal
  allow-list, using `value_overrides` in the mapping.
* `eligibility` and `notes` can be mapped, and eligibility is validated against
  the state vocabulary, but neither is WRITTEN by commit. Student creation goes
  through `StudentRepository.create_student` and nothing else; adding
  eligibility links would be a second write path, which is a separate change.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import logging
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.mcp.privacy import (
    IMPORT_FIELDS,
    NEVER_REVEAL_FIELDS,
    SAFE_REVEAL_FIELDS,
    header_reveal_rows,
    mask_header,
    mask_value,
    reveal_samples,
    revealable_value,
    summarize_column,
)
from app.models.eligibility_category import EligibilityCategory
from app.models.import_batch import (
    STATUS_COMMITTED,
    STATUS_DISCARDED,
    STATUS_MAPPED,
    STATUS_PENDING_UPLOAD,
    STATUS_UPLOADED,
    STATUS_VALIDATED,
    ImportBatch,
    ImportRow,
)
from app.models.school import School
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user_student_access import UserStudentAccess
from app.repositories.student_repository import StudentRepository
from app.schemas.student import StudentCreate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# policy constants
# ---------------------------------------------------------------------------
# A distinct prefix from the `slp_` API key on purpose. These two credentials
# open completely different doors -- one is a caseload, the other is a single
# file upload -- and a door that can tell them apart by their first five
# characters cannot be talked into accepting the wrong one.
UPLOAD_TOKEN_PREFIX = "slpu_"
UPLOAD_TOKEN_BYTES = 20

# Thirty minutes is long enough to walk to the machine the file is on and short
# enough that a link left in a chat log is dead by the time anybody finds it.
UPLOAD_TOKEN_TTL = timedelta(minutes=30)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DATA_ROWS = 5000

# The longest a single cell may be before it is truncated at parse time. Five
# compressed megabytes of xlsx can hold a single cell of several hundred
# megabytes -- zip is very good at repetition -- and `MAX_DATA_ROWS` does not
# bound that, because it counts rows. Nothing an import writes is longer than a
# school's name, so anything past this is not caseload data.
MAX_CELL_CHARS = 4096

# What a CSV's one sheet is called. NOT the file's name: the upload route takes
# a filename from a browser, "Ramirez caseload.csv" is a child's name, and the
# sheet name is returned over MCP by `preview` and echoed by every mapping
# error that lists a file's sheets. An xlsx carries its own sheet names, which
# the therapist typed inside the workbook; a CSV has none, and inventing one out
# of the filename was the only path by which the filename crossed the wire.
CSV_SHEET_NAME = "Sheet1"

# A guard, not a limit anybody will meet: a sheet with more columns than this
# is not a caseload and parsing all of it would be a way to make the server
# work hard on request.
MAX_COLUMNS = 512

# How many issue records `validate_import` returns before it stops listing them
# individually. The grouped counts and `unresolvedValues` still describe the
# whole file, so nothing is hidden -- what is capped is the size of the payload
# a model has to read.
MAX_LISTED_ISSUES = 200

# How many DISTINCT unresolved spellings `validate` quotes per field before it
# stops listing them and reports a count instead.
#
# This is a volume gate, not a privacy one -- the privacy gate is
# `privacy.revealable_value`. It exists because the grouped list used to be
# uncapped: a column mislabelled `school` came back as every distinct value in
# it, deduplicated and sorted, which is a roster export in one tool call. A
# caseload does not span more buildings than this, so a file that does is a
# mapping that is wrong, and the count says so without printing the column.
UNRESOLVED_LIST_LIMIT = 25

# The length limits `app/schemas/student.py` puts on the fields this import
# writes. Checked HERE so an over-long cell is a validation issue with a row
# number on it, rather than a pydantic `ValidationError` raised in the middle
# of the commit loop -- whose message quotes the offending value back to the
# model, which for `first_name` is precisely the thing that must never travel.
#
# `test_blind_import_adversarial.py` asserts this table still agrees with the
# schema, so a limit changed there fails a test here rather than reopening the
# hole quietly.
MAX_IMPORTABLE_VALUE_LENGTH = {
    "first_name": 100,
    "last_name": 100,
    "uic": 50,
    "grade_level": 35,
    "enrollment_status": 20,
}

# The encodings a district export actually arrives in, tried in order. Same
# list the rigid CSV importer uses.
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "latin-1")

# Fuzzy-match floor for "did you mean this school?". Below this the suggestion
# is noise and it is better to say nothing.
_FUZZY_CUTOFF = 0.6

# Issue kinds that stop a commit. Everything else is a warning: the value is
# dropped and the student is still created.
BLOCKING_ISSUES = frozenset(
    {
        "missing_required",
        "unknown_school",
        "unknown_teacher",
        "unknown_case_manager",
        "duplicate_uic_in_file",
        "duplicate_uic_existing",
        "value_too_long",
        "no_data_rows",
    }
)

# Fields that must be resolvable to a row in this database before a commit.
_LOOKUP_FIELDS = ("school", "teacher", "case_manager")


class BlindImportError(ValueError):
    """
    Anything a tool should report to the agent as a plain refusal.

    A `ValueError`, like every other refusal the MCP surface raises, so the
    `@tool()` wrapper's error sanitizer and the SDK's error path treat it
    identically to the ones the rest of `app/mcp/server.py` composes. A second
    exception hierarchy here would be a second thing to remember to filter.
    """


class UploadRejected(Exception):
    """A browser upload that cannot be accepted, with the status to answer."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# the upload token
# ---------------------------------------------------------------------------
def generate_upload_token() -> str:
    return f"{UPLOAD_TOKEN_PREFIX}{secrets.token_hex(UPLOAD_TOKEN_BYTES)}"


def hash_upload_token(secret: str) -> str:
    """sha256 hex of the exact string the browser will present in the URL."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def looks_like_upload_token(value: Optional[str]) -> bool:
    return bool(value) and value.startswith(UPLOAD_TOKEN_PREFIX)


def create_batch(db: Session, user_id: int, now: Optional[datetime] = None):
    """
    A new empty batch plus the one-shot secret that opens its upload page.

    Returns `(batch, secret)`. The secret is never stored and this is the only
    moment it exists on the server -- exactly the API-key contract, because it
    is the same risk: a link that can be replayed is a link that can be
    uploaded to twice.
    """
    stamp = now or datetime.utcnow()
    secret = generate_upload_token()
    batch = ImportBatch(
        user_id=user_id,
        status=STATUS_PENDING_UPLOAD,
        upload_token_hash=hash_upload_token(secret),
        token_expires_at=stamp + UPLOAD_TOKEN_TTL,
        sheet_count=0,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch, secret


def resolve_upload_batch(
    db: Session, secret: str, now: Optional[datetime] = None
) -> ImportBatch:
    """
    A presented upload secret -> the batch it opens, or a refusal that says why.

    The three refusals are deliberately DIFFERENT messages, because the person
    reading them is the therapist herself in her own browser, not an attacker
    probing an API: "this link has expired" and "this link has already been
    used" are the two things she needs to know in order to do the right next
    thing, and neither tells anybody anything they could not learn by trying.

    Single use is enforced by the batch's STATUS rather than by clearing the
    digest at upload time. Clearing it would make a second POST indistinguishable
    from a forged token -- both would be "unknown link" -- when what actually
    happened is "you already uploaded this file", which is worth saying. The
    digest is cleared when the batch reaches a terminal state, so a committed or
    discarded batch carries no live credential.
    """
    stamp = now or datetime.utcnow()
    if not looks_like_upload_token(secret):
        raise UploadRejected("That upload link is not valid.", 404)

    batch = (
        db.query(ImportBatch)
        .filter(ImportBatch.upload_token_hash == hash_upload_token(secret))
        .one_or_none()
    )
    if batch is None:
        raise UploadRejected(
            "That upload link is not valid. Ask Claude for a fresh one.", 404
        )
    if batch.token_expires_at is not None and batch.token_expires_at <= stamp:
        raise UploadRejected(
            "That upload link has expired. Upload links are good for 30 minutes "
            "-- ask Claude for a fresh one.",
            410,
        )
    if batch.status != STATUS_PENDING_UPLOAD:
        raise UploadRejected(
            "That upload link has already been used. Each link accepts exactly "
            "one file. Ask Claude for a fresh one if you need to upload again.",
            409,
        )
    return batch


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def column_letter(index: int) -> str:
    """0 -> "A", 25 -> "Z", 26 -> "AA". The spreadsheet's own column names.

    Written here rather than imported from openpyxl so the preview, mapping and
    validation halves of this module do not depend on the xlsx reader at all --
    a CSV import must work whether or not openpyxl is installed.
    """
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _cell_text(value: Any) -> Optional[str]:
    """
    One parsed cell -> the string that is stored, or None for empty.

    Everything is normalised to text at PARSE time rather than at read time, so
    `cells_json` is a plain array of strings and nulls and nothing downstream
    has to know whether a date arrived as a datetime (xlsx) or as "3/17/2011"
    (csv). Floats that are whole numbers lose their ".0" because a grade level
    of "4.0" is an artefact of the spreadsheet, not of the child.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    text = str(value).strip()
    if len(text) > MAX_CELL_CHARS:
        text = text[:MAX_CELL_CHARS]
    return text or None


def _trim(cells: list[Optional[str]]) -> list[Optional[str]]:
    while cells and cells[-1] is None:
        cells.pop()
    return cells


def parse_upload(filename: str, content: bytes) -> list[dict]:
    """
    An uploaded file -> `[{"name": sheet, "rows": [(row_index, cells), ...]}]`.

    Row indices are 1-based and are the spreadsheet's OWN numbering, including
    the blank rows that are skipped, so every issue this server reports later
    points at the row the therapist can see on her screen.
    """
    name = (filename or "").strip()
    lowered = name.lower()
    if lowered.endswith(".csv"):
        sheets = _parse_csv(content)
    elif lowered.endswith(".xlsx"):
        sheets = _parse_xlsx(content)
    elif lowered.endswith(".xls"):
        raise UploadRejected(
            "That is an old-format .xls file. Open it in Excel or Sheets and "
            "save it as .xlsx or .csv, then upload it again."
        )
    else:
        raise UploadRejected(
            "That file type is not supported. Upload a .xlsx spreadsheet or a "
            ".csv file."
        )

    total = sum(len(sheet["rows"]) for sheet in sheets)
    if total == 0:
        raise UploadRejected(
            "That file has no rows in it. Check that you uploaded the right "
            "file and that it is not empty."
        )
    return sheets


def _too_many_rows() -> UploadRejected:
    """
    The refusal both parsers raise the moment the row budget is spent.

    Raised from INSIDE the read loop rather than counted afterwards: a workbook
    of a thousand tabs holding ten rows each is ten thousand rows, and reading
    all of them into memory before objecting to their number is a way to be
    made to do a lot of work by a five-megabyte file.
    """
    return UploadRejected(
        f"That file has more than the {MAX_DATA_ROWS} rows this import accepts, "
        f"counting every sheet in it. Split it and upload the parts separately."
    )


def _parse_xlsx(content: bytes) -> list[dict]:
    """
    Every sheet of an xlsx, values only.

    `data_only=True` is doing real work: without it a formula cell yields its
    FORMULA, and `=CONCATENATE(B2," ",A2)` names a child as surely as the cell
    it computes. With it, a formula yields the value Excel last cached, or None
    if the file was written by a library that never calculated one -- and None
    is the safe answer.

    `read_only=True` also means a merged range reads as its value in the
    top-left cell and None everywhere else, which is what the preview should
    see: one value, in one place.
    """
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - openpyxl is a pinned dep
        raise UploadRejected(
            "This server cannot read .xlsx files right now. Save the file as "
            ".csv and upload that instead.",
            500,
        ) from exc

    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(content), data_only=True, read_only=True
        )
    except Exception as exc:
        raise UploadRejected(
            "That file could not be opened as a spreadsheet. It may be "
            "password-protected or damaged."
        ) from exc

    sheets: list[dict] = []
    budget = MAX_DATA_ROWS
    try:
        for worksheet in workbook.worksheets:
            rows: list[tuple[int, list[Optional[str]]]] = []
            for index, raw in enumerate(worksheet.iter_rows(values_only=True), start=1):
                cells = _trim([_cell_text(value) for value in raw[:MAX_COLUMNS]])
                if not cells:
                    continue
                if budget <= 0:
                    raise _too_many_rows()
                budget -= 1
                rows.append((index, cells))
            sheets.append({"name": worksheet.title, "rows": rows})
    finally:
        workbook.close()
    return sheets


def _decode(content: bytes) -> str:
    for encoding in _CSV_ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadRejected(
        "That file's text could not be decoded. Re-save it as UTF-8 CSV and "
        "upload it again."
    )


def _parse_csv(content: bytes) -> list[dict]:
    """A CSV is one sheet, and its name is a constant -- see `CSV_SHEET_NAME`."""
    text = _decode(content)
    rows: list[tuple[int, list[Optional[str]]]] = []
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        for index, raw in enumerate(reader, start=1):
            cells = _trim([_cell_text(value) for value in raw[:MAX_COLUMNS]])
            if not cells:
                continue
            if len(rows) >= MAX_DATA_ROWS:
                raise _too_many_rows()
            rows.append((index, cells))
    except csv.Error as exc:
        # An unterminated quote turns the rest of the file into one field, and
        # `csv` refuses past 128 KB. Its message is about the file, so it is not
        # repeated to anybody.
        raise UploadRejected(
            "That CSV could not be read -- a quotation mark is probably left "
            "open somewhere in it. Re-save it from Excel or Sheets and upload "
            "it again."
        ) from exc
    return [{"name": CSV_SHEET_NAME, "rows": rows}]


def store_rows(
    db: Session,
    batch: ImportBatch,
    sheets: Sequence[dict],
    filename: Optional[str] = None,
) -> int:
    """
    Parsed sheets -> `import_rows`, and the batch marked uploaded.

    This is the moment the PII lands, and it lands in one column of one table
    with nothing else reading it. The token is spent here: the batch leaves
    `pending_upload`, which is what makes the link single-use.

    `filename` is recorded for the app's own UI and for support ("which file
    was this?"). It is never returned over MCP -- a filename is user-typed text
    and "Ramirez caseload.xlsx" is a name.
    """
    stored = 0
    for sheet in sheets:
        for row_index, cells in sheet["rows"]:
            db.add(
                ImportRow(
                    batch_id=batch.id,
                    sheet_name=sheet["name"][:255],
                    row_index=row_index,
                    cells_json=json.dumps(cells, ensure_ascii=False),
                )
            )
            stored += 1
    if filename:
        batch.filename = filename.strip()[:255]
    batch.sheet_count = len(sheets)
    batch.status = STATUS_UPLOADED
    batch.updated_at = datetime.utcnow()
    db.commit()
    return stored


# ---------------------------------------------------------------------------
# reading a batch back
# ---------------------------------------------------------------------------
def get_batch(db: Session, batch_id: int, user_id: int) -> ImportBatch:
    """
    One of the CALLER'S OWN batches, or a refusal that says nothing else.

    Scoped by user_id with no admin override, deliberately: an import is a
    personal working document, half-finished and full of somebody's raw roster,
    and there is no administrative question it answers. Somebody else's batch id
    is "not found", which leaks nothing about whether it exists.
    """
    batch = (
        db.query(ImportBatch)
        .filter(ImportBatch.id == batch_id, ImportBatch.user_id == user_id)
        .one_or_none()
    )
    if batch is None:
        raise BlindImportError(
            f"Import batch {batch_id} was not found. Call create_import_upload "
            f"to start one, and note that a batch belongs to the person who "
            f"created it."
        )
    return batch


def _rows(db: Session, batch: ImportBatch, sheet: Optional[str] = None) -> list[ImportRow]:
    query = db.query(ImportRow).filter(ImportRow.batch_id == batch.id)
    if sheet is not None:
        query = query.filter(ImportRow.sheet_name == sheet)
    return query.order_by(ImportRow.sheet_name, ImportRow.row_index).all()


def _cells(row: ImportRow) -> list[Optional[str]]:
    try:
        loaded = json.loads(row.cells_json or "[]")
    except ValueError:  # pragma: no cover - written by this module only
        return []
    return loaded if isinstance(loaded, list) else []


def _by_sheet(rows: Iterable[ImportRow]) -> dict[str, list[ImportRow]]:
    out: dict[str, list[ImportRow]] = {}
    for row in rows:
        out.setdefault(row.sheet_name, []).append(row)
    return out


def _require_uploaded(batch: ImportBatch) -> None:
    if batch.status == STATUS_PENDING_UPLOAD:
        raise BlindImportError(
            f"Import batch {batch.id} has no file yet. The upload link from "
            f"create_import_upload has to be opened in a browser and a "
            f"spreadsheet uploaded before there is anything to look at."
        )
    if batch.status in (STATUS_COMMITTED, STATUS_DISCARDED):
        raise BlindImportError(
            f"Import batch {batch.id} is {batch.status} and cannot be changed. "
            f"Start a new one with create_import_upload."
        )


# ---------------------------------------------------------------------------
# preview -- shapes only
# ---------------------------------------------------------------------------
def preview(db: Session, batch: ImportBatch, header_candidate_limit: int = 3) -> dict:
    """
    What the file LOOKS like, with nothing in it quoted.

    Every cell is reduced to a shape. The one exception is header text, which is
    unavoidable -- nobody can map "Xxxxx Xxxx" to `first_name` -- and is
    therefore fenced in as tightly as it can be: only rows that clear all four
    gates in `app.mcp.privacy.header_reveal_rows` are printed, the scan stops at
    the real header row so nothing below it is ever considered, each cell is
    capped in length, and the whole payload goes through the roster scrub on the
    way out like everything else.

    The filename is deliberately NOT reported. "Ramirez caseload.xlsx" is a
    name, and there is nothing an agent does better for knowing it.
    """
    _require_uploaded(batch)
    grouped = _by_sheet(_rows(db, batch))

    sheets = []
    for sheet_name, rows in grouped.items():
        parsed = [(row.row_index, _cells(row)) for row in rows]
        width = max((len(cells) for _, cells in parsed), default=0)
        by_index = dict(parsed)

        # `header_reveal_rows` is the whole verbatim-reveal policy of this
        # stage, and it is deliberately much stricter than "looks like a header
        # row" -- see its docstring. Rows it does not name are described by
        # shape like every other row in the file.
        revealable = header_reveal_rows(parsed, limit=header_candidate_limit)
        candidates = [
            {
                "rowIndex": row_index,
                "headerTexts": {
                    column_letter(i): mask_header(by_index[row_index][i])
                    for i in range(len(by_index[row_index]))
                    if mask_value(by_index[row_index][i]) is not None
                },
            }
            for row_index in revealable
        ]

        # Column headers come from the LAST revealed row, which is the widest
        # one the scan reached: banners come first and the real header row is
        # what the scan stops at. A sheet with no revealable row has no header
        # this server is willing to print, and its columns are identified by
        # letter alone -- the safe answer, because the alternative is printing
        # row 1, and row 1 of a header-less caseload export is a child.
        header_cells: list[Optional[str]] = []
        header_row_index: Optional[int] = None
        if candidates:
            header_row_index = candidates[-1]["rowIndex"]
            header_cells = by_index[header_row_index]

        # Everything from the header row upwards is preamble -- headings,
        # banners, the district's logo row -- and none of it is data. Summarising
        # it alongside the students would put "Xxxxxxx" (the word "Student") and
        # the banner's shape into the same frequency table as the column they
        # sit above, which is exactly the signal the agent is reading.
        body = [
            cells
            for index, cells in parsed
            if header_row_index is None or index > header_row_index
        ]
        columns = [
            summarize_column(
                column_letter(i),
                header_cells[i] if i < len(header_cells) else None,
                [cells[i] if i < len(cells) else None for cells in body],
            )
            for i in range(width)
        ]

        sheets.append(
            {
                "sheet": sheet_name,
                "dimensions": {"rows": len(parsed), "columns": width},
                "firstRowIndex": parsed[0][0] if parsed else None,
                "lastRowIndex": parsed[-1][0] if parsed else None,
                "headerRowCandidates": candidates,
                "suggestedHeaderRow": header_row_index,
                "suggestedDataStartRow": (
                    header_row_index + 1 if header_row_index is not None else None
                ),
                "columns": columns,
            }
        )

    return {
        "batchId": batch.id,
        "status": batch.status,
        "sheetCount": batch.sheet_count,
        "everyValueIsMasked": True,
        "mappableFields": list(IMPORT_FIELDS),
        "revealableAfterMapping": sorted(SAFE_REVEAL_FIELDS),
        "neverRevealed": sorted(NEVER_REVEAL_FIELDS),
        "sheets": sheets,
    }


# ---------------------------------------------------------------------------
# mapping
# ---------------------------------------------------------------------------
_COLUMN_PATTERN = re.compile(r"^[A-Z]{1,3}$")

# Fields that may legitimately be claimed by more than one column. A caseload
# export routinely carries two comment columns and several columns nobody
# wants; everything else answers one question and a second answer is a mistake
# worth catching now rather than at commit.
_REPEATABLE_FIELDS = frozenset({"ignore", "notes"})


def _column_index(letter: str) -> int:
    total = 0
    for char in letter:
        total = total * 26 + (ord(char) - ord("A") + 1)
    return total - 1


def normalize_mapping(db: Session, batch: ImportBatch, mapping: Any) -> dict:
    """
    A mapping proposal -> the stored, validated form, or a refusal.

    Everything is checked here rather than at commit: the sheet exists, the
    rows are in range, every column letter is a column letter, every field name
    is one of `IMPORT_FIELDS`, no field is claimed twice, and the mapping names
    enough to produce a student at all.
    """
    if not isinstance(mapping, dict):
        raise BlindImportError(
            "mapping must be an object with keys: sheet, header_row, "
            "data_start_row, columns."
        )

    grouped = _by_sheet(_rows(db, batch))
    if not grouped:
        raise BlindImportError(f"Import batch {batch.id} has no rows to map.")

    sheet = mapping.get("sheet")
    if sheet is None and len(grouped) == 1:
        sheet = next(iter(grouped))
    if sheet not in grouped:
        raise BlindImportError(
            f"This file has no sheet called {sheet!r}. Its sheets are: "
            f"{', '.join(sorted(grouped))}."
        )

    indices = [row.row_index for row in grouped[sheet]]
    first, last = min(indices), max(indices)

    header_row = mapping.get("header_row")
    data_start_row = mapping.get("data_start_row")
    if header_row is not None:
        header_row = _as_int(header_row, "header_row")
    if data_start_row is None:
        data_start_row = (header_row + 1) if header_row is not None else first
    data_start_row = _as_int(data_start_row, "data_start_row")

    if data_start_row > last:
        raise BlindImportError(
            f"data_start_row={data_start_row} is past the end of sheet {sheet!r}, "
            f"whose last row is {last}. There would be no students to import."
        )

    raw_columns = mapping.get("columns")
    if not isinstance(raw_columns, dict) or not raw_columns:
        raise BlindImportError(
            "mapping.columns must be an object of column letter -> field name, "
            f"for example {{\"A\": \"last_name\", \"B\": \"first_name\"}}. Valid "
            f"field names: {', '.join(IMPORT_FIELDS)}."
        )

    columns: dict[str, str] = {}
    claimed: dict[str, str] = {}
    for raw_letter, raw_field in raw_columns.items():
        letter = str(raw_letter).strip().upper()
        if not _COLUMN_PATTERN.match(letter):
            raise BlindImportError(
                f"{raw_letter!r} is not a spreadsheet column letter. Use the "
                f"letters get_import_preview reported (A, B, C...)."
            )
        field = str(raw_field).strip().lower()
        if field not in IMPORT_FIELDS:
            raise BlindImportError(
                f"{raw_field!r} is not a field this import understands. Valid "
                f"field names: {', '.join(IMPORT_FIELDS)}."
            )
        if field not in _REPEATABLE_FIELDS and field in claimed:
            raise BlindImportError(
                f"Columns {claimed[field]} and {letter} are both mapped to "
                f"{field!r}. Map one of them to 'ignore'."
            )
        claimed.setdefault(field, letter)
        columns[letter] = field

    has_split_name = "first_name" in claimed and "last_name" in claimed
    has_full_name = "full_name_last_first" in claimed or "full_name_first_last" in claimed
    if not (has_split_name or has_full_name):
        raise BlindImportError(
            "A student needs a name. Map either first_name AND last_name, or a "
            "single column to full_name_last_first / full_name_first_last."
        )
    if has_split_name and has_full_name:
        raise BlindImportError(
            "Map the name EITHER as first_name + last_name OR as one "
            "full_name_* column, not both -- otherwise there are two answers "
            "to what a student is called."
        )

    overrides = _normalize_overrides(mapping.get("value_overrides"))

    return {
        "sheet": sheet,
        "header_row": header_row,
        "data_start_row": data_start_row,
        "columns": columns,
        "value_overrides": overrides,
    }


def _as_int(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BlindImportError(f"{field} must be a row number (got {value!r}).") from None
    if number < 1:
        raise BlindImportError(f"{field} must be 1 or more (got {number}).")
    return number


def _normalize_overrides(raw: Any) -> dict[str, dict[str, str]]:
    """
    `value_overrides` -> `{field: {raw value (casefolded): replacement}}`.

    This is how an unresolvable school or teacher gets resolved, and it is
    deliberately the ONLY way. `validate_import` reports the file's spelling of
    an unknown building (which it may, because school is on the reveal
    allow-list) together with the closest existing name; the agent proposes the
    correction here; the mapping records it. Nothing is written to `schools` or
    `teachers` by an import -- a fuzzy match is a suggestion, not a licence to
    create a second Northgate Elementary.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise BlindImportError(
            "value_overrides must be an object of field -> {file value: existing "
            "name}, for example {\"school\": {\"Nrthgate El\": \"Northgate "
            "Elementary\"}}."
        )
    out: dict[str, dict[str, str]] = {}
    for field, pairs in raw.items():
        name = str(field).strip().lower()
        if name not in _LOOKUP_FIELDS:
            raise BlindImportError(
                f"value_overrides can only correct {', '.join(_LOOKUP_FIELDS)} "
                f"(got {field!r}). Those are the fields whose values this server "
                f"is allowed to show you, which is what makes them the fields "
                f"you can correct."
            )
        if not isinstance(pairs, dict):
            raise BlindImportError(
                f"value_overrides[{name!r}] must be an object of file value -> "
                f"existing name."
            )
        out[name] = {
            str(k).strip().casefold(): str(v).strip()
            for k, v in pairs.items()
            if str(v).strip()
        }
    return out


def stored_mapping(batch: ImportBatch) -> Optional[dict]:
    if not batch.mapping_json:
        return None
    try:
        loaded = json.loads(batch.mapping_json)
    except ValueError:  # pragma: no cover - written by this module only
        return None
    return loaded if isinstance(loaded, dict) else None


def set_mapping(db: Session, batch: ImportBatch, mapping: Any, contexts) -> dict:
    """
    Record the mapping, and open the allow-listed columns -- only now.

    The reveal is gated on TWO things happening in this order: somebody decided
    what a column means, and the meaning is in `SAFE_REVEAL_FIELDS`. That
    ordering is the whole privacy argument. Before a mapping exists, no column
    can be shown, because "the column of Capitalised Words" is as likely to be
    surnames as buildings. After it, the fields that name an institution can be
    shown and the fields that name a child still cannot -- `NEVER_REVEAL_FIELDS`
    is checked independently rather than as the complement of the allow-list, so
    a field added to `IMPORT_FIELDS` and forgotten here is invisible by default
    rather than public by default.
    """
    _require_uploaded(batch)
    normalized = normalize_mapping(db, batch, mapping)

    batch.mapping_json = json.dumps(normalized, ensure_ascii=False)
    batch.status = STATUS_MAPPED
    batch.updated_at = datetime.utcnow()
    db.commit()

    rows = [
        row
        for row in _rows(db, batch, normalized["sheet"])
        if row.row_index >= normalized["data_start_row"]
    ]
    parsed = [_cells(row) for row in rows]

    revealed: dict[str, dict] = {}
    withheld: dict[str, str] = {}
    for letter, field in sorted(normalized["columns"].items()):
        index = _column_index(letter)
        values = [cells[index] if index < len(cells) else None for cells in parsed]
        if field in SAFE_REVEAL_FIELDS and field not in NEVER_REVEAL_FIELDS:
            populated = [value for value in values if mask_value(value) is not None]
            unrevealable = sum(
                1 for value in populated if not revealable_value(value)
            )
            revealed[letter] = {
                "field": field,
                "sampleValues": reveal_samples(values, contexts),
                "distinctValues": len(
                    {(value or "").strip().casefold() for value in populated}
                ),
                # Cells in an allow-listed column that still may not be quoted
                # -- dates, long identifiers, prose. A count above zero means
                # the column is not what the mapping says it is.
                "valuesNotShowable": unrevealable,
            }
        else:
            withheld[letter] = field

    return {
        "batchId": batch.id,
        "status": batch.status,
        "mapping": normalized,
        "dataRows": len(rows),
        "revealedColumns": revealed,
        "withheldColumns": withheld,
        "note": (
            "Sample values are shown only for columns mapped to organisational "
            "fields. Names, dates of birth, identifiers and free-text notes are "
            "never shown, whatever they are mapped to."
        ),
    }


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%m-%d-%y",
    "%m.%d.%Y",
    "%d %B %Y",
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%Y/%m/%d",
)

_DATE_FIELDS = (
    "date_of_birth",
    "iep_date",
    "annual_review_due_date",
    "reevaluation_due_date",
)


def parse_date_value(text: Optional[str]) -> Optional[date]:
    """A cell -> a date, across the spellings a school export actually uses."""
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    # An xlsx date arrives as "2011-03-17 00:00:00" when the cell carried a
    # time component the therapist never sees.
    cleaned = cleaned.split(" 00:00:00")[0].strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        return None


def split_name(field: str, value: str) -> tuple[Optional[str], Optional[str]]:
    """
    One "full name" cell -> (first, last), per the convention the mapping named.

    A comma always wins: "Ramirez, Sofia" is unambiguous whichever convention
    the column was mapped as, and district exports mix the two within one file
    often enough that trusting the mapping over the punctuation would corrupt
    rows. Without a comma the mapping decides which end the surname is on.
    """
    text = (value or "").strip()
    if not text:
        return None, None
    if "," in text:
        last, _, first = text.partition(",")
        return first.strip() or None, last.strip() or None

    parts = text.split()
    if len(parts) == 1:
        return (parts[0], None) if field == "full_name_first_last" else (None, parts[0])
    if field == "full_name_last_first":
        return " ".join(parts[1:]).strip() or None, parts[0]
    return " ".join(parts[:-1]).strip() or None, parts[-1]


class _Lookups:
    """
    The existing schools, teachers and eligibility categories, indexed once.

    Built per validation run rather than cached: an import is the exact moment
    somebody is also adding buildings and staff, and a stale index would report
    a school as unknown minutes after it was created.
    """

    def __init__(self, db: Session) -> None:
        self.schools: dict[str, int] = {}
        self.school_names: list[str] = []
        for school in db.query(School).filter(School.is_active.is_(True)).all():
            name = (school.name or "").strip()
            if not name:
                continue
            self.school_names.append(name)
            self.schools.setdefault(name.casefold(), school.id)
            self.schools.setdefault(
                name.replace("(CLOSED)", "").strip().casefold(), school.id
            )

        self.teachers: dict[str, int] = {}
        self.teacher_names: list[str] = []
        for teacher in db.query(Teacher).filter(Teacher.is_active.is_(True)).all():
            first = (teacher.first_name or "").strip()
            last = (teacher.last_name or "").strip()
            full = f"{first} {last}".strip()
            if not full:
                continue
            self.teacher_names.append(full)
            for spelling in (full, f"{last}, {first}", f"{last},{first}"):
                self.teachers.setdefault(spelling.strip().casefold(), teacher.id)

        self.eligibilities: set[str] = set()
        self.eligibility_names: list[str] = []
        for category in db.query(EligibilityCategory).all():
            name = (getattr(category, "name", "") or "").strip()
            if not name:
                continue
            self.eligibility_names.append(name)
            self.eligibilities.add(name.casefold())
            code = (getattr(category, "code", "") or "").strip()
            if code:
                self.eligibilities.add(code.casefold())

    def school_id(self, value: str) -> Optional[int]:
        return self.schools.get(value.strip().casefold())

    def teacher_id(self, value: str) -> Optional[int]:
        return self.teachers.get(value.strip().casefold())

    def closest(self, value: str, field: str) -> Optional[str]:
        pool = {
            "school": self.school_names,
            "teacher": self.teacher_names,
            "case_manager": self.teacher_names,
            "eligibility": self.eligibility_names,
        }.get(field, [])
        if not pool:
            return None
        matches = difflib.get_close_matches(value, pool, n=1, cutoff=_FUZZY_CUTOFF)
        return matches[0] if matches else None


def _row_fields(cells: Sequence[Optional[str]], mapping: dict) -> dict[str, Any]:
    """One row -> `{field: (column letter, value)}`, first non-empty column wins."""
    out: dict[str, tuple[str, str]] = {}
    for letter, field in mapping["columns"].items():
        if field == "ignore":
            continue
        index = _column_index(letter)
        value = cells[index] if index < len(cells) else None
        if value is None or not str(value).strip():
            continue
        out.setdefault(field, (letter, str(value).strip()))
    return out


def _apply_override(mapping: dict, field: str, value: str) -> str:
    return mapping.get("value_overrides", {}).get(field, {}).get(value.casefold(), value)


# The fields whose unresolved values are GROUPED and (subject to
# `revealable_value`) quoted. The lookup three are blocking; eligibility is a
# warning, which is why it needs the same grouping -- an ungrouped warning that
# quotes a value once per row is an uncapped channel wearing a small name.
_REPORTABLE_VALUE_FIELDS = _LOOKUP_FIELDS + ("eligibility",)


def _group(
    bucket: dict, value: str, row_index: int, lookups: "_Lookups", field: str
) -> None:
    """Add one unresolvable cell to its field's grouped list, once per spelling."""
    entry = bucket.get(value.casefold())
    if entry is None:
        entry = {"rows": [], "_sort": value.casefold()}
        entry.update(_reported_value(value))
        # A "did you mean" is only meaningful next to the value it is a
        # suggestion for, and only the database's own names are ever in it.
        if "value" in entry:
            entry["closestExistingMatch"] = lookups.closest(value, field)
        bucket[value.casefold()] = entry
    entry["rows"].append(row_index)


def _over_length(field: str, value: Optional[str]) -> bool:
    limit = MAX_IMPORTABLE_VALUE_LENGTH.get(field)
    return bool(limit) and value is not None and len(value) > limit


def _length_issue(field: str, value: str, fields: dict) -> dict:
    """A cell the student schema will refuse -- by length, never by content."""
    found = fields.get(field)
    issue = {
        "issue": "value_too_long",
        "field": field,
        "length": len(value),
        "maximum": MAX_IMPORTABLE_VALUE_LENGTH[field],
    }
    if found:
        issue["column"] = found[0]
    return issue


def _reported_value(value: str) -> dict:
    """
    One unresolvable cell -> what may be said about it.

    The value itself when it looks like the kind of thing its field is for, and
    its SHAPE when it does not. A column of birthdays labelled `school` is
    reported as "row 7, column D, shape ####-##-##", which is exactly what an
    unparseable date is reported as and exactly as much as anybody needs to
    notice that the mapping is wrong.
    """
    if revealable_value(value):
        return {"value": value}
    return {"valueShape": mask_value(value)}


def validate(db: Session, batch: ImportBatch) -> dict:
    """
    Every row checked, and every problem reported WITHOUT the value that caused it.

    The discipline is uniform: a row number always; a column letter always; the
    VALUE never, in the per-row record. So an unparseable birthday is reported
    as "row 14, column D, shape ##-##-##", which is enough to fix it and
    useless to anyone else.

    An unknown school is still reported by name, because a name the agent
    cannot see is a name the agent cannot reconcile -- but ONCE, in the grouped
    `unresolvedValues`, and subject to two gates the per-row record could not
    apply: `revealable_value` (is this cell shaped like a building at all, or is
    it a birthday in a column somebody has labelled `school`?) and
    `UNRESOLVED_LIST_LIMIT` (a caseload does not span twenty-five buildings, so
    a file that does is a mapping that is wrong).

    A duplicate against an existing student is reported as that student's ALIAS.
    """
    _require_uploaded(batch)
    mapping = stored_mapping(batch)
    if mapping is None:
        raise BlindImportError(
            f"Import batch {batch.id} has no mapping yet. Call "
            f"get_import_preview, work out what the columns mean, then "
            f"set_import_mapping."
        )

    lookups = _Lookups(db)
    rows = [
        row
        for row in _rows(db, batch, mapping["sheet"])
        if row.row_index >= mapping["data_start_row"]
    ]

    issues: list[dict] = []
    per_row: dict[int, list[dict]] = {}
    uic_first_seen: dict[str, int] = {}
    unresolved: dict[str, dict[str, dict]] = {
        field: {} for field in _REPORTABLE_VALUE_FIELDS
    }
    ready = 0

    def record(row_index: int, payload: dict) -> None:
        payload = {"row": row_index, "sheet": mapping["sheet"], **payload}
        payload["blocking"] = payload["issue"] in BLOCKING_ISSUES
        issues.append(payload)
        per_row.setdefault(row_index, []).append(payload)

    for row in rows:
        fields = _row_fields(_cells(row), mapping)
        blocking_here = 0

        # ---- name --------------------------------------------------------
        first = last = None
        for field in ("full_name_last_first", "full_name_first_last"):
            if field in fields:
                first, last = split_name(field, fields[field][1])
        if "first_name" in fields:
            first = fields["first_name"][1]
        if "last_name" in fields:
            last = fields["last_name"][1]
        for label, value in (("first_name", first), ("last_name", last)):
            if not value:
                record(row.row_index, {"issue": "missing_required", "field": label})
                blocking_here += 1
            elif _over_length(label, value):
                record(
                    row.row_index,
                    _length_issue(label, value, fields),
                )
                blocking_here += 1
        for label in ("uic", "grade_level", "enrollment_status"):
            if label in fields and _over_length(label, fields[label][1]):
                record(row.row_index, _length_issue(label, fields[label][1], fields))
                blocking_here += 1

        # ---- dates -------------------------------------------------------
        for field in _DATE_FIELDS:
            if field not in fields:
                continue
            letter, raw = fields[field]
            if parse_date_value(raw) is None:
                record(
                    row.row_index,
                    {
                        "issue": "unparseable_date",
                        "field": field,
                        "column": letter,
                        # The SHAPE, never the value: a birthday is a direct
                        # identifier and "##-##-##" says everything needed to
                        # fix the column.
                        "shape": mask_value(raw),
                    },
                )

        # ---- schools, teachers, case managers ----------------------------
        for field in _LOOKUP_FIELDS:
            if field not in fields:
                continue
            letter, raw = fields[field]
            value = _apply_override(mapping, field, raw)
            found = (
                lookups.school_id(value)
                if field == "school"
                else lookups.teacher_id(value)
            )
            if found is not None:
                continue
            kind = f"unknown_{field}" if field != "case_manager" else "unknown_case_manager"
            # The per-ROW record says where the problem is; the value is said
            # ONCE, in the grouped list below. Repeating it per row turned a
            # deduplicated list of a handful of buildings into one quoted cell
            # per student, which is a column export with a row number attached.
            record(
                row.row_index,
                {"issue": kind, "field": field, "column": letter},
            )
            _group(unresolved[field], value, row.row_index, lookups, field)
            blocking_here += 1

        # ---- eligibility (validated, not written) ------------------------
        if "eligibility" in fields:
            letter, raw = fields["eligibility"]
            if raw.strip().casefold() not in lookups.eligibilities:
                record(
                    row.row_index,
                    {
                        "issue": "unknown_eligibility",
                        "field": "eligibility",
                        "column": letter,
                    },
                )
                _group(unresolved["eligibility"], raw, row.row_index, lookups, "eligibility")

        # ---- UIC ---------------------------------------------------------
        if "uic" in fields:
            _, raw_uic = fields["uic"]
            key = raw_uic.strip().casefold()
            previous = uic_first_seen.get(key)
            if previous is not None:
                record(
                    row.row_index,
                    {
                        "issue": "duplicate_uic_in_file",
                        "field": "uic",
                        # Row pair, not the identifier.
                        "duplicateOfRow": previous,
                    },
                )
                blocking_here += 1
            else:
                uic_first_seen[key] = row.row_index
            # DELIBERATELY UNFILTERED BY ARCHIVE. `students.uic` is UNIQUE, so
            # an archived student still owns their UIC and re-creating it would
            # fail on the constraint -- but the more important reason is
            # clinical: a child who left the caseload in September and is on
            # this term's spreadsheet is a RETURNING student, not a new one, and
            # the therapist needs to be told to restore the record rather than
            # start a second one beside it.
            existing = (
                db.query(Student).filter(Student.uic == raw_uic.strip()).one_or_none()
            )
            if existing is not None:
                issue = {
                    "issue": "duplicate_uic_existing",
                    "field": "uic",
                    # The alias, which is what a student IS over this
                    # connection.
                    "existingStudent": existing.alias,
                    "existingStudentId": existing.id,
                    "existingStudentArchived": existing.archived_at is not None,
                }
                if existing.archived_at is not None:
                    issue["existingStudentArchiveEventId"] = existing.archive_event_id
                    issue["hint"] = (
                        f"{existing.alias} is ARCHIVED, not absent. Restore that "
                        f"record instead of importing this row as a new student."
                    )
                record(row.row_index, issue)
                blocking_here += 1

        row.issues_json = json.dumps(per_row.get(row.row_index, []), ensure_ascii=False)
        if blocking_here == 0:
            ready += 1

    if not rows:
        record(mapping["data_start_row"], {"issue": "no_data_rows"})

    blocking = [issue for issue in issues if issue["blocking"]]
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["issue"]] = counts.get(issue["issue"], 0) + 1

    batch.status = STATUS_VALIDATED if not blocking else STATUS_MAPPED
    batch.updated_at = datetime.utcnow()
    db.commit()

    listed = {field: _listed(bucket) for field, bucket in unresolved.items()}

    return {
        "batchId": batch.id,
        "status": batch.status,
        "readyToCommit": not blocking,
        "rowsChecked": len(rows),
        "rowsReady": ready,
        "blockingIssues": len(blocking),
        "warnings": len(issues) - len(blocking),
        "issueCounts": counts,
        "issues": issues[:MAX_LISTED_ISSUES],
        "issuesTruncated": len(issues) > MAX_LISTED_ISSUES,
        "unresolvedValues": {
            field: listed[field] for field in unresolved if unresolved[field]
        },
        "unresolvedValuesTruncated": {
            field: len(unresolved[field]) - len(listed[field])
            for field in unresolved
            if len(unresolved[field]) > len(listed[field])
        },
        "howToResolve": (
            "Unknown school / teacher / case_manager values are the blocking "
            "ones. Call list_schools and list_teachers, then call "
            "set_import_mapping again with value_overrides mapping the file's "
            "spelling onto the existing name. This import never creates a "
            "school or a teacher. An entry reported as `valueShape` rather than "
            "`value` is a cell that does not look like a building, an adult or "
            "a category at all -- a birthday or an identifier, say -- which "
            "means the column is mapped to the wrong field. Fix the mapping; "
            "the value will not be shown."
        ),
    }


def _listed(bucket: dict) -> list[dict]:
    """One field's grouped unresolved values, sorted and capped."""
    ordered = sorted(bucket.values(), key=lambda item: item["_sort"])
    return [
        {key: value for key, value in entry.items() if key != "_sort"}
        for entry in ordered[:UNRESOLVED_LIST_LIMIT]
    ]


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------
def _student_payload(fields: dict, mapping: dict, lookups: _Lookups) -> StudentCreate:
    first = last = None
    for field in ("full_name_last_first", "full_name_first_last"):
        if field in fields:
            first, last = split_name(field, fields[field][1])
    if "first_name" in fields:
        first = fields["first_name"][1]
    if "last_name" in fields:
        last = fields["last_name"][1]

    def value(field: str) -> Optional[str]:
        found = fields.get(field)
        return found[1] if found else None

    def linked(field: str) -> Optional[int]:
        raw = value(field)
        if raw is None:
            return None
        resolved = _apply_override(mapping, field, raw)
        return (
            lookups.school_id(resolved)
            if field == "school"
            else lookups.teacher_id(resolved)
        )

    return StudentCreate(
        first=first,
        last=last,
        uic=value("uic"),
        grade_level=value("grade_level"),
        enrollment_status=value("enrollment_status") or "Active",
        date_of_birth=parse_date_value(value("date_of_birth")),
        school_id=linked("school"),
        teacher_id=linked("teacher"),
        case_manager_id=linked("case_manager"),
        iep_date=parse_date_value(value("iep_date")),
        annual_review_due_date=parse_date_value(value("annual_review_due_date")),
        reevaluation_due_date=parse_date_value(value("reevaluation_due_date")),
    )


def commit(db: Session, batch: ImportBatch, user_id: int, confirm: bool) -> dict:
    """
    Create the students, all of them or none of them.

    Re-validates first, whatever `status` says: a batch validated ten minutes
    ago may have had its school deleted since, and "the row said it was fine
    earlier" is not a reason to write a half-linked record.

    Students are created through `StudentRepository.create_student`, the same
    call `app/routers/students.py` and the rigid CSV import make -- there is no
    import-only write path, so a rule added to student creation applies here on
    the same deploy. That repository commits per student, which is what makes
    the all-or-nothing promise below a COMPENSATING one rather than a single
    transaction: if any row fails, every student this call created is deleted
    again before the error is raised. It is safe precisely because these rows
    are seconds old and nothing else references them yet.
    """
    _require_uploaded(batch)
    outcome = validate(db, batch)
    mapping = stored_mapping(batch) or {}
    lookups = _Lookups(db)

    rows = [
        row
        for row in _rows(db, batch, mapping["sheet"])
        if row.row_index >= mapping["data_start_row"]
    ]
    payloads = [(row, _row_fields(_cells(row), mapping)) for row in rows]

    if not outcome["readyToCommit"]:
        return {
            "committed": False,
            "batchId": batch.id,
            "reason": (
                f"{outcome['blockingIssues']} blocking issue(s) have to be "
                f"resolved first. Call validate_import to see them."
            ),
            "blockingIssues": outcome["blockingIssues"],
            "issueCounts": outcome["issueCounts"],
            "unresolvedValues": outcome["unresolvedValues"],
        }

    if confirm is not True:
        return {
            "committed": False,
            "batchId": batch.id,
            "reason": "confirm must be true to create these students",
            "wouldCreate": {
                "students": len(payloads),
                "sheet": mapping["sheet"],
                "fromRows": [rows[0].row_index, rows[-1].row_index] if rows else [],
                "fieldsThatWillBeWritten": sorted(
                    {
                        field
                        for _, fields in payloads
                        for field in fields
                        if field not in ("notes", "eligibility")
                    }
                ),
                "fieldsMappedButNotWritten": sorted(
                    {
                        field
                        for _, fields in payloads
                        for field in fields
                        if field in ("notes", "eligibility")
                    }
                ),
                "warnings": outcome["warnings"],
            },
            "note": (
                "Show this to the therapist and get an answer before sending "
                "confirm=true. Names, birthdays and identifiers are written "
                "from the stored file; you will get back aliases, not names."
            ),
        }

    repository = StudentRepository(db)
    created: list[int] = []
    grants: list[int] = []
    failed_row: Optional[int] = None
    try:
        for row, fields in payloads:
            failed_row = row.row_index
            student = repository.create_student(_student_payload(fields, mapping, lookups))
            created.append(student.id)
            row.resolved_student_id = student.id

            grant = UserStudentAccess(
                user_id=user_id,
                student_id=student.id,
                granted_by_user_id=user_id,
                is_active=True,
            )
            db.add(grant)
            db.flush()
            grants.append(grant.id)

        batch.status = STATUS_COMMITTED
        batch.committed_at = datetime.utcnow()
        batch.updated_at = batch.committed_at
        batch.committed_student_ids_json = json.dumps(created)
        # The upload credential is meaningless now, and a digest nobody can use
        # is a digest better not kept.
        batch.upload_token_hash = None
        db.commit()
    except Exception:
        # The message is NOT re-raised. Whatever failed had a row of the
        # spreadsheet in its hands: pydantic quotes the offending cell back as
        # `input_value=...` and a driver quotes the whole parameter tuple, so
        # the exception text of a failed student INSERT is a child's name, date
        # of birth and identifier in one string, heading for a transcript. The
        # row number is what makes it fixable and is all that goes out.
        logger.exception(
            "Blind import commit failed for batch %s at row %s", batch.id, failed_row
        )
        db.rollback()
        try:
            _undo(db, created, grants)
        except Exception:
            logger.exception("Blind import undo failed for batch %s", batch.id)
            raise BlindImportError(
                f"Row {failed_row} of sheet {mapping['sheet']!r} could not be "
                f"written, and undoing the {len(created)} student(s) already "
                f"created failed as well. Do not retry this import. Tell the "
                f"therapist to check her caseload in the SLP Pro app and say "
                f"that the import was interrupted."
            ) from None
        raise BlindImportError(
            f"Row {failed_row} of sheet {mapping['sheet']!r} could not be written, "
            f"so nothing was: the {len(created)} student(s) this call had already "
            f"created have been removed again. The row's values are not repeated "
            f"here. Check that row in the spreadsheet -- a cell far longer than "
            f"the field it is mapped to is the usual cause -- and run "
            f"validate_import again."
        ) from None

    return {
        "committed": True,
        "batchId": batch.id,
        "created": len(created),
        # Aliases, never names. This is the payload most likely to be quoted
        # straight back into a chat, so it carries the identity the rest of
        # this server uses and nothing else.
        "students": [f"student_{student_id}" for student_id in created],
        "accessGranted": len(grants),
        "warnings": outcome["warnings"],
        "nextStep": (
            "The staged copy of the spreadsheet is still on the server. Call "
            "discard_import with confirm=true to destroy it."
        ),
    }


def _undo(db: Session, student_ids: Sequence[int], grant_ids: Sequence[int]) -> None:
    """
    Put the caseload back the way it was after a half-finished commit.

    Deletes rather than archives: these students were created seconds ago by a
    call that failed, nothing references them, and leaving them behind would
    mean a retry produces duplicates of children who were never successfully
    imported in the first place.
    """
    if not student_ids and not grant_ids:
        return
    try:
        if grant_ids:
            db.query(UserStudentAccess).filter(
                UserStudentAccess.id.in_(list(grant_ids))
            ).delete(synchronize_session=False)
        if student_ids:
            # The staged rows point at the students this call created, and
            # `import_rows.resolved_student_id` is a real foreign key. Deleting
            # the students without clearing it first fails on the constraint --
            # which is how a compensating delete came to leave behind exactly
            # the half-imported caseload it exists to prevent.
            db.query(ImportRow).filter(
                ImportRow.resolved_student_id.in_(list(student_ids))
            ).update({"resolved_student_id": None}, synchronize_session=False)
            db.query(Student).filter(Student.id.in_(list(student_ids))).delete(
                synchronize_session=False
            )
        db.commit()
    except Exception:  # pragma: no cover - the rollback of a rollback
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# discard
# ---------------------------------------------------------------------------
def discard(db: Session, batch: ImportBatch, confirm: bool) -> dict:
    """
    Destroy the staged rows. That is the point, not a side effect.

    `import_rows.cells_json` is the only place in this system holding a
    verbatim copy of somebody's roster export. Discarding is how a therapist
    gets rid of it on demand instead of waiting for a retention job, so the
    destructive half of this tool is the FEATURE and the confirmation exists
    only because a batch mid-import is also work somebody has done.
    """
    row_count = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).count()
    summary = {
        "batchId": batch.id,
        "status": batch.status,
        "stagedRows": row_count,
        "sheets": batch.sheet_count,
        "committedStudents": len(json.loads(batch.committed_student_ids_json or "[]")),
    }
    if confirm is not True:
        return {
            "discarded": False,
            "reason": (
                "confirm must be true to delete this batch and the staged copy "
                "of the spreadsheet"
            ),
            "wouldDelete": summary,
        }

    db.query(ImportRow).filter(ImportRow.batch_id == batch.id).delete(
        synchronize_session=False
    )
    db.delete(batch)
    db.commit()
    return {
        "discarded": True,
        "removed": summary,
        "note": (
            "The staged spreadsheet rows are gone. Students already created by "
            "commit_import are unaffected -- they are ordinary caseload records "
            "now."
        ),
    }
