"""Add the staged-import tables (blind caseload import).

Two tables behind `app/services/blind_import.py`:

* `import_batches` — one uploaded spreadsheet on its way into the caseload,
  plus the sha256 of the one-shot upload token that opens its browser upload
  page. The digest is UNIQUE (a credential that could open two batches is not a
  credential) and NULLABLE (it is cleared once the batch is committed or
  discarded and the token is meaningless).
* `import_rows` — the parsed spreadsheet, verbatim, one row per row.
  `cells_json` holds real names, dates of birth and state identifiers. It is
  the one column in this schema deliberately walled off from the MCP surface:
  nothing returns it, `app/mcp/privacy.py` drops the key structurally, and
  `backend/tests/test_blind_import.py` asserts the absence.

Type style follows the rest of the schema: `Unicode`/`UnicodeText` rather than
`String`/`Text`, `DateTime` for stamps, and the NVARCHAR(max) variant trick
from b4e7a1c93d20 for the large JSON columns, because plain `UnicodeText`
renders the deprecated NTEXT on SQL Server unless the dialect has resolved
`deprecate_large_types` against a live server.

`import_rows.batch_id` is a plain FK with no ON DELETE CASCADE: discarding a
batch deletes its rows explicitly in one statement first (see
`blind_import.discard`), and a database-side cascade would be a second,
untested path to destroying the same data.

Revision ID: c9f2a7d81b45
Revises: b4e7a1c93d20
Create Date: 2026-08-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision: str = "c9f2a7d81b45"
down_revision: Union[str, None] = "b4e7a1c93d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Identical to what the model declares. See the docstring.
_LARGE_TEXT = sa.UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending_upload",
        ),
        # sha256 hex, 64 characters. NULL once spent.
        sa.Column("upload_token_hash", sa.String(length=64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("filename", sa.Unicode(length=255), nullable=True),
        sa.Column("sheet_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("mapping_json", _LARGE_TEXT, nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=True),
        sa.Column("committed_student_ids_json", _LARGE_TEXT, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_batches_id"), "import_batches", ["id"])
    op.create_index(op.f("ix_import_batches_user_id"), "import_batches", ["user_id"])
    op.create_index(op.f("ix_import_batches_status"), "import_batches", ["status"])
    # UNIQUE: the digest is the credential, and one credential opens one batch.
    op.create_index(
        op.f("ix_import_batches_upload_token_hash"),
        "import_batches",
        ["upload_token_hash"],
        unique=True,
    )

    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("sheet_name", sa.Unicode(length=255), nullable=False),
        # 1-based, the spreadsheet's own numbering, so a reported issue points
        # at the row the therapist can see on her screen.
        sa.Column("row_index", sa.Integer(), nullable=False),
        # THE PII. See the module docstring.
        sa.Column("cells_json", _LARGE_TEXT, nullable=False),
        sa.Column("issues_json", _LARGE_TEXT, nullable=True),
        sa.Column("resolved_student_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["resolved_student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_rows_id"), "import_rows", ["id"])
    op.create_index(op.f("ix_import_rows_batch_id"), "import_rows", ["batch_id"])
    op.create_index(
        op.f("ix_import_rows_resolved_student_id"),
        "import_rows",
        ["resolved_student_id"],
    )


def downgrade() -> None:
    # Rows first: they hold the FK into batches.
    op.drop_index(op.f("ix_import_rows_resolved_student_id"), table_name="import_rows")
    op.drop_index(op.f("ix_import_rows_batch_id"), table_name="import_rows")
    op.drop_index(op.f("ix_import_rows_id"), table_name="import_rows")
    op.drop_table("import_rows")

    op.drop_index(
        op.f("ix_import_batches_upload_token_hash"), table_name="import_batches"
    )
    op.drop_index(op.f("ix_import_batches_status"), table_name="import_batches")
    op.drop_index(op.f("ix_import_batches_user_id"), table_name="import_batches")
    op.drop_index(op.f("ix_import_batches_id"), table_name="import_batches")
    op.drop_table("import_batches")
