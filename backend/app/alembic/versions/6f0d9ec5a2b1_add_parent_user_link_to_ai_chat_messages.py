"""Add parent user linkage to ai chat messages.

Revision ID: 6f0d9ec5a2b1
Revises: a4c9d52f0e11
Create Date: 2026-02-15 21:25:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f0d9ec5a2b1"
down_revision: Union[str, None] = "a4c9d52f0e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_messages",
        sa.Column("parent_user_message_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_ai_chat_messages_parent_user_message_id"),
        "ai_chat_messages",
        ["parent_user_message_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_ai_chat_messages_parent_user_message_id",
        "ai_chat_messages",
        "ai_chat_messages",
        ["parent_user_message_id"],
        ["id"],
    )

    # Backfill legacy rows by pairing each assistant with the most recent
    # unmatched user message in the same chat session.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, chat_session_id, role
            FROM ai_chat_messages
            ORDER BY chat_session_id ASC, id ASC
            """
        )
    ).mappings().all()

    pending_user_by_session: dict[int, int | None] = {}
    updates: list[dict[str, int]] = []
    for row in rows:
        message_id = int(row["id"])
        session_id = int(row["chat_session_id"])
        role = str(row["role"] or "").lower()

        if role == "user":
            pending_user_by_session[session_id] = message_id
            continue
        if role != "assistant":
            continue

        pending_user_id = pending_user_by_session.get(session_id)
        if pending_user_id is None:
            continue
        updates.append(
            {
                "assistant_id": message_id,
                "parent_user_message_id": pending_user_id,
            }
        )
        pending_user_by_session[session_id] = None

    if updates:
        connection.execute(
            sa.text(
                """
                UPDATE ai_chat_messages
                SET parent_user_message_id = :parent_user_message_id
                WHERE id = :assistant_id
                """
            ),
            updates,
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_chat_messages_parent_user_message_id",
        "ai_chat_messages",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_ai_chat_messages_parent_user_message_id"), table_name="ai_chat_messages")
    op.drop_column("ai_chat_messages", "parent_user_message_id")
