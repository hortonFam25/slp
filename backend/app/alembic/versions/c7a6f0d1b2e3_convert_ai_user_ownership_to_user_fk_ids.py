"""Convert AI ownership columns from auth strings to user FK ids.

Revision ID: c7a6f0d1b2e3
Revises: b1f6e2d9c4aa
Create Date: 2026-02-16 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a6f0d1b2e3"
down_revision: Union[str, None] = "b1f6e2d9c4aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Add temporary integer columns.
    op.add_column("ai_chat_sessions", sa.Column("user_id_int", sa.Integer(), nullable=True))
    op.add_column("ai_saved_progress_notes", sa.Column("user_id_int", sa.Integer(), nullable=True))
    op.add_column("ai_saved_progress_notes", sa.Column("created_by_int", sa.Integer(), nullable=True))

    # Backfill temp columns from legacy auth id strings.
    connection.execute(
        sa.text(
            """
            UPDATE s
            SET s.user_id_int = u.id
            FROM ai_chat_sessions s
            INNER JOIN users u ON u.external_auth_id = s.user_id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE n
            SET n.user_id_int = u.id
            FROM ai_saved_progress_notes n
            INNER JOIN users u ON u.external_auth_id = n.user_id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE n
            SET n.created_by_int = u.id
            FROM ai_saved_progress_notes n
            INNER JOIN users u ON u.external_auth_id = n.created_by
            """
        )
    )

    # Fallback for any unmatched legacy values (safe for near-empty AI data).
    connection.execute(
        sa.text(
            """
            DECLARE @fallback_user_id INT;
            SELECT TOP 1 @fallback_user_id = id FROM users ORDER BY id ASC;
            UPDATE ai_chat_sessions
            SET user_id_int = @fallback_user_id
            WHERE user_id_int IS NULL;
            UPDATE ai_saved_progress_notes
            SET user_id_int = @fallback_user_id
            WHERE user_id_int IS NULL;
            """
        )
    )

    # Swap to the new integer user_id columns.
    op.drop_index(op.f("ix_ai_chat_sessions_user_id"), table_name="ai_chat_sessions")
    op.drop_column("ai_chat_sessions", "user_id")
    op.alter_column("ai_chat_sessions", "user_id_int", new_column_name="user_id", existing_type=sa.Integer())
    op.alter_column("ai_chat_sessions", "user_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(op.f("ix_ai_chat_sessions_user_id"), "ai_chat_sessions", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_ai_chat_sessions_user_id_users",
        "ai_chat_sessions",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_index(op.f("ix_ai_saved_progress_notes_user_id"), table_name="ai_saved_progress_notes")
    op.drop_column("ai_saved_progress_notes", "user_id")
    op.alter_column("ai_saved_progress_notes", "user_id_int", new_column_name="user_id", existing_type=sa.Integer())
    op.alter_column("ai_saved_progress_notes", "user_id", existing_type=sa.Integer(), nullable=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_user_id"), "ai_saved_progress_notes", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_ai_saved_progress_notes_user_id_users",
        "ai_saved_progress_notes",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_column("ai_saved_progress_notes", "created_by")
    op.alter_column(
        "ai_saved_progress_notes",
        "created_by_int",
        new_column_name="created_by",
        existing_type=sa.Integer(),
    )
    op.create_foreign_key(
        "fk_ai_saved_progress_notes_created_by_users",
        "ai_saved_progress_notes",
        "users",
        ["created_by"],
        ["id"],
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Add temporary legacy string columns.
    op.add_column("ai_chat_sessions", sa.Column("user_id_str", sa.String(length=100), nullable=True))
    op.add_column("ai_saved_progress_notes", sa.Column("user_id_str", sa.String(length=100), nullable=True))
    op.add_column("ai_saved_progress_notes", sa.Column("created_by_str", sa.String(length=100), nullable=True))

    # Backfill string columns from users table.
    connection.execute(
        sa.text(
            """
            UPDATE s
            SET s.user_id_str = u.external_auth_id
            FROM ai_chat_sessions s
            INNER JOIN users u ON u.id = s.user_id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE n
            SET n.user_id_str = u.external_auth_id
            FROM ai_saved_progress_notes n
            INNER JOIN users u ON u.id = n.user_id
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE n
            SET n.created_by_str = u.external_auth_id
            FROM ai_saved_progress_notes n
            INNER JOIN users u ON u.id = n.created_by
            """
        )
    )

    op.drop_constraint("fk_ai_chat_sessions_user_id_users", "ai_chat_sessions", type_="foreignkey")
    op.drop_index(op.f("ix_ai_chat_sessions_user_id"), table_name="ai_chat_sessions")
    op.drop_column("ai_chat_sessions", "user_id")
    op.alter_column("ai_chat_sessions", "user_id_str", new_column_name="user_id", existing_type=sa.String(length=100))
    op.alter_column("ai_chat_sessions", "user_id", existing_type=sa.String(length=100), nullable=False)
    op.create_index(op.f("ix_ai_chat_sessions_user_id"), "ai_chat_sessions", ["user_id"], unique=False)

    op.drop_constraint("fk_ai_saved_progress_notes_user_id_users", "ai_saved_progress_notes", type_="foreignkey")
    op.drop_index(op.f("ix_ai_saved_progress_notes_user_id"), table_name="ai_saved_progress_notes")
    op.drop_column("ai_saved_progress_notes", "user_id")
    op.alter_column(
        "ai_saved_progress_notes",
        "user_id_str",
        new_column_name="user_id",
        existing_type=sa.String(length=100),
    )
    op.alter_column("ai_saved_progress_notes", "user_id", existing_type=sa.String(length=100), nullable=False)
    op.create_index(op.f("ix_ai_saved_progress_notes_user_id"), "ai_saved_progress_notes", ["user_id"], unique=False)

    op.drop_constraint("fk_ai_saved_progress_notes_created_by_users", "ai_saved_progress_notes", type_="foreignkey")
    op.drop_column("ai_saved_progress_notes", "created_by")
    op.alter_column(
        "ai_saved_progress_notes",
        "created_by_str",
        new_column_name="created_by",
        existing_type=sa.String(length=100),
    )

