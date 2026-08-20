"""Add the OAuth facade tables (clients, codes, refresh tokens).

Also completes api_tokens: the two OAuth columns that migration a7f31c9e5d02
had to leave as bare integers - the tables they point at did not exist yet -
get their foreign keys here, now that they do.

The FK add runs inside `batch_alter_table` so it works on both engines this
schema is created against: SQL Server takes it as a plain ALTER TABLE ADD
CONSTRAINT, while SQLite (which cannot alter constraints at all) is given
alembic's copy-and-rename treatment automatically. Nothing about the columns
changes on either - they stay nullable, and every existing row keeps its NULLs.

Revision ID: c5a91b3e77d4
Revises: a7f31c9e5d02
Create Date: 2026-08-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5a91b3e77d4"
down_revision: Union[str, None] = "a7f31c9e5d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- oauth_clients ----------------------------------------------------
    # One row per RFC 7591 dynamic registration. Every client is public, so
    # there is no secret column to store or leak.
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        # 32 hex characters of randomness, the public identifier.
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("client_name", sa.String(length=120), nullable=True),
        # JSON arrays exactly as registered. Text -> VARCHAR(MAX) on SQL
        # Server: RFC 7591 puts no cap on how many callbacks a client lists.
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column("grant_types", sa.Text(), nullable=True),
        sa.Column("response_types", sa.Text(), nullable=True),
        sa.Column("token_endpoint_auth_method", sa.String(length=32), nullable=False),
        # Written by the application (datetime.utcnow), NOT by a server
        # default: the rest of this schema uses GETDATE(), which is SQL Server
        # only, and these rows are also created against SQLite in development.
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_oauth_clients_client_id"),
    )
    op.create_index(op.f("ix_oauth_clients_id"), "oauth_clients", ["id"], unique=False)
    op.create_index(
        op.f("ix_oauth_clients_client_id"), "oauth_clients", ["client_id"], unique=False
    )

    # ---- oauth_codes ------------------------------------------------------
    # The ten-minute single-use ticket. Stored as a digest; the plaintext only
    # ever exists in the redirect URL and in the client's memory.
    op.create_table(
        "oauth_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("oauth_client_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=8), nullable=False),
        sa.Column("resource", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        # NULL until redeemed. The row is never deleted: the replay rule needs
        # to be able to tell "used once" from "never existed".
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["oauth_client_id"], ["oauth_clients.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_oauth_codes_code_hash"),
    )
    op.create_index(op.f("ix_oauth_codes_id"), "oauth_codes", ["id"], unique=False)
    op.create_index(
        op.f("ix_oauth_codes_code_hash"), "oauth_codes", ["code_hash"], unique=False
    )
    op.create_index(
        op.f("ix_oauth_codes_oauth_client_id"),
        "oauth_codes",
        ["oauth_client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_codes_user_id"), "oauth_codes", ["user_id"], unique=False
    )

    # ---- oauth_refresh_tokens --------------------------------------------
    # The long half of a grant. Rotates on every use; `oauth_code_id` is the
    # grant family that "revoke this connection" updates.
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("oauth_client_id", sa.Integer(), nullable=False),
        sa.Column("oauth_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["oauth_client_id"], ["oauth_clients.id"]),
        sa.ForeignKeyConstraint(["oauth_code_id"], ["oauth_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_oauth_refresh_tokens_token_hash"),
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_id"), "oauth_refresh_tokens", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_token_hash"),
        "oauth_refresh_tokens",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_oauth_client_id"),
        "oauth_refresh_tokens",
        ["oauth_client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_oauth_code_id"),
        "oauth_refresh_tokens",
        ["oauth_code_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_user_id"),
        "oauth_refresh_tokens",
        ["user_id"],
        unique=False,
    )

    # ---- the FKs a7f31c9e5d02 could not add ------------------------------
    with op.batch_alter_table("api_tokens") as batch:
        batch.create_foreign_key(
            "fk_api_tokens_oauth_client_id",
            "oauth_clients",
            ["oauth_client_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_api_tokens_oauth_code_id", "oauth_codes", ["oauth_code_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("api_tokens") as batch:
        batch.drop_constraint("fk_api_tokens_oauth_code_id", type_="foreignkey")
        batch.drop_constraint("fk_api_tokens_oauth_client_id", type_="foreignkey")

    op.drop_index(
        op.f("ix_oauth_refresh_tokens_user_id"), table_name="oauth_refresh_tokens"
    )
    op.drop_index(
        op.f("ix_oauth_refresh_tokens_oauth_code_id"), table_name="oauth_refresh_tokens"
    )
    op.drop_index(
        op.f("ix_oauth_refresh_tokens_oauth_client_id"),
        table_name="oauth_refresh_tokens",
    )
    op.drop_index(
        op.f("ix_oauth_refresh_tokens_token_hash"), table_name="oauth_refresh_tokens"
    )
    op.drop_index(op.f("ix_oauth_refresh_tokens_id"), table_name="oauth_refresh_tokens")
    op.drop_table("oauth_refresh_tokens")

    op.drop_index(op.f("ix_oauth_codes_user_id"), table_name="oauth_codes")
    op.drop_index(op.f("ix_oauth_codes_oauth_client_id"), table_name="oauth_codes")
    op.drop_index(op.f("ix_oauth_codes_code_hash"), table_name="oauth_codes")
    op.drop_index(op.f("ix_oauth_codes_id"), table_name="oauth_codes")
    op.drop_table("oauth_codes")

    op.drop_index(op.f("ix_oauth_clients_client_id"), table_name="oauth_clients")
    op.drop_index(op.f("ix_oauth_clients_id"), table_name="oauth_clients")
    op.drop_table("oauth_clients")
