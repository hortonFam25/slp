"""
Staged caseload imports — the two tables the AI is never allowed to read.

The point of this pair is a very specific separation. `import_rows.cells_json`
holds the SPREADSHEET AS IT WAS UPLOADED: real names, real dates of birth, real
state identifiers, whatever else the district's export happened to contain. It
arrives over an ordinary browser upload, from the therapist's own machine, and
it stays here. No MCP tool returns it, `app.mcp.privacy` drops the key
outright if one ever tries, and `backend/tests/test_blind_import.py` asserts
that.

What the model DOES see is derived: the SHAPE of each value ("Xxxxxxx",
"##/##/####"), counts, row numbers, and — only after a mapping has been agreed
— sample values from the handful of columns that carry organisational context
rather than a child's identity (see `SAFE_REVEAL_FIELDS` in
`app.mcp.privacy`).

Lifecycle, which `status` names:

    pending_upload -> uploaded -> mapped -> validated -> committed
                                                     \\-> discarded (any time)

`upload_token_hash` is the same scheme as an API key (`slp_`-style secret,
sha256 at rest) with two differences: it expires in thirty minutes, and it is
good for exactly one upload. Enforcement of the "one" is the status check —
the token only opens a batch that is still `pending_upload` — which is what
lets a second POST be answered "you already uploaded this" instead of an
indistinguishable 404. The digest is cleared when the batch reaches a terminal
state, so a committed or discarded batch has no credential left at all.

Deleting a batch deletes its rows, and that is a FEATURE: discarding an import
is how a therapist destroys the staged copy of her roster on demand.
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Unicode,
    UnicodeText,
)
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import relationship

from app.db.base import Base

# UnicodeText renders NTEXT on SQL Server unless the dialect resolved
# `deprecate_large_types` against a live server. NTEXT is deprecated and
# refuses most string operators, so pin NVARCHAR(max) explicitly and leave
# sqlite on TEXT. Same trick as migration b4e7a1c93d20.
_LARGE_TEXT = UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")

# The states a batch moves through. Strings rather than an Enum so a value
# added later does not need a type change on SQL Server.
STATUS_PENDING_UPLOAD = "pending_upload"
STATUS_UPLOADED = "uploaded"
STATUS_MAPPED = "mapped"
STATUS_VALIDATED = "validated"
STATUS_COMMITTED = "committed"
STATUS_DISCARDED = "discarded"

ALL_STATUSES = (
    STATUS_PENDING_UPLOAD,
    STATUS_UPLOADED,
    STATUS_MAPPED,
    STATUS_VALIDATED,
    STATUS_COMMITTED,
    STATUS_DISCARDED,
)


class ImportBatch(Base):
    """One spreadsheet, on its way from a browser upload into the caseload."""

    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)

    # Imports are PERSONAL. A batch belongs to the therapist who asked for the
    # upload link, and every tool scopes to the caller's own user_id —
    # including an admin's, who gets no override here. There is nothing
    # administrative about somebody else's half-imported roster.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(
        String(32),
        nullable=False,
        default=STATUS_PENDING_UPLOAD,
        server_default=STATUS_PENDING_UPLOAD,
        index=True,
    )

    # sha256 hex of the upload secret — 64 characters. NULL once the batch has
    # reached a terminal state and the credential is meaningless.
    upload_token_hash = Column(String(64), nullable=True, unique=True, index=True)
    token_expires_at = Column(DateTime, nullable=True)

    # What the browser called the file. NOT returned by any MCP tool: a
    # filename is user-typed text and "Ramirez caseload.xlsx" is a name.
    filename = Column(Unicode(255), nullable=True)
    sheet_count = Column(Integer, nullable=False, default=0, server_default="0")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # The agreed column mapping, as JSON. Structure, never values.
    mapping_json = Column(_LARGE_TEXT, nullable=True)

    committed_at = Column(DateTime, nullable=True)
    # JSON list of the student ids this batch created, so a committed batch can
    # say what it did without re-deriving it from the rows.
    committed_student_ids_json = Column(_LARGE_TEXT, nullable=True)

    rows = relationship(
        "ImportRow",
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )


class ImportRow(Base):
    """
    One row of one sheet, exactly as it was parsed.

    `cells_json` is the PII. It is a JSON array of strings-or-nulls, one per
    column, and it exists so that `commit_import` can write the real values
    into the caseload without those values ever having been shown to a model.
    Nothing else reads it, and nothing returns it.
    """

    __tablename__ = "import_rows"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(
        Integer, ForeignKey("import_batches.id"), nullable=False, index=True
    )

    sheet_name = Column(Unicode(255), nullable=False)
    # 1-based, as the spreadsheet numbers it, so an issue this server reports
    # points at the row the therapist can see on her own screen.
    row_index = Column(Integer, nullable=False)

    cells_json = Column(_LARGE_TEXT, nullable=False)
    issues_json = Column(_LARGE_TEXT, nullable=True)

    resolved_student_id = Column(
        Integer, ForeignKey("students.id"), nullable=True, index=True
    )

    batch = relationship("ImportBatch", back_populates="rows")
