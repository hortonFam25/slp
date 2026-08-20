"""Add users and user student access tables.

Revision ID: b1f6e2d9c4aa
Revises: 2d3b6ac8f4ce
Create Date: 2026-02-15 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1f6e2d9c4aa"
down_revision: Union[str, None] = "2d3b6ac8f4ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_auth_id", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="basic"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.Column("modified_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_external_auth_id"), "users", ["external_auth_id"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)

    op.create_table(
        "user_student_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.Column("modified_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "student_id", name="uq_user_student_access_user_student"),
    )
    op.create_index(op.f("ix_user_student_access_id"), "user_student_access", ["id"], unique=False)
    op.create_index(op.f("ix_user_student_access_user_id"), "user_student_access", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_student_access_student_id"), "user_student_access", ["student_id"], unique=False)
    op.create_index(op.f("ix_user_student_access_is_active"), "user_student_access", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_student_access_is_active"), table_name="user_student_access")
    op.drop_index(op.f("ix_user_student_access_student_id"), table_name="user_student_access")
    op.drop_index(op.f("ix_user_student_access_user_id"), table_name="user_student_access")
    op.drop_index(op.f("ix_user_student_access_id"), table_name="user_student_access")
    op.drop_table("user_student_access")

    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_external_auth_id"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

