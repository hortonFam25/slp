"""Add roles and teacher_roles tables.

Revision ID: f2d4b8c9a1e0
Revises: e1b9d3f4a2c7
Create Date: 2026-02-17 14:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2d4b8c9a1e0"
down_revision: Union[str, None] = "e1b9d3f4a2c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.Column("modified_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_id"), "roles", ["id"], unique=False)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)
    op.create_index(op.f("ix_roles_is_active"), "roles", ["is_active"], unique=False)

    op.create_table(
        "teacher_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_date", sa.DateTime(), nullable=False, server_default=sa.text("GETDATE()")),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "role_id", name="uq_teacher_roles_teacher_role"),
    )
    op.create_index(op.f("ix_teacher_roles_id"), "teacher_roles", ["id"], unique=False)
    op.create_index(op.f("ix_teacher_roles_teacher_id"), "teacher_roles", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_teacher_roles_role_id"), "teacher_roles", ["role_id"], unique=False)

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO roles (name)
            VALUES
              ('Teacher'),
              ('Case Manager'),
              ('Social Worker'),
              ('Psychologist')
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_teacher_roles_role_id"), table_name="teacher_roles")
    op.drop_index(op.f("ix_teacher_roles_teacher_id"), table_name="teacher_roles")
    op.drop_index(op.f("ix_teacher_roles_id"), table_name="teacher_roles")
    op.drop_table("teacher_roles")

    op.drop_index(op.f("ix_roles_is_active"), table_name="roles")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_id"), table_name="roles")
    op.drop_table("roles")

