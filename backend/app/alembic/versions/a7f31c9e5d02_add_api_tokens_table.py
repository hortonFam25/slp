"""Add api_tokens table (personal connection keys for /mcp).

Revision ID: a7f31c9e5d02
Revises: f2d4b8c9a1e0
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f31c9e5d02"
down_revision: Union[str, None] = "f2d4b8c9a1e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        # sha256 hex of the presented secret — always 64 characters.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        # First 12 characters of the plaintext, for display only.
        sa.Column("prefix", sa.String(length=12), nullable=False),
        # Written by the application (datetime.utcnow), NOT by a server
        # default: the rest of this schema uses GETDATE(), which is SQL Server
        # only, and these rows are also created against SQLite in development.
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="manual"),
        # NULL = never expires, which is what every manually minted key carries.
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        # Deliberately plain nullable integers with NO ForeignKey: the
        # oauth_clients / oauth_codes tables do not exist yet. Adding the
        # constraints is a later, additive migration once they do.
        sa.Column("oauth_client_id", sa.Integer(), nullable=True),
        sa.Column("oauth_code_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_api_tokens_token_hash"),
    )
    op.create_index(op.f("ix_api_tokens_id"), "api_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_api_tokens_user_id"), "api_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_api_tokens_token_hash"), "api_tokens", ["token_hash"], unique=False)
    op.create_index(
        op.f("ix_api_tokens_oauth_client_id"), "api_tokens", ["oauth_client_id"], unique=False
    )
    op.create_index(
        op.f("ix_api_tokens_oauth_code_id"), "api_tokens", ["oauth_code_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_api_tokens_oauth_code_id"), table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_oauth_client_id"), table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_token_hash"), table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_user_id"), table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_id"), table_name="api_tokens")
    op.drop_table("api_tokens")
