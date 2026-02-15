"""add_teacher_case_manager_relationships_to_students

Revision ID: 9c69ae0cd521
Revises: 8f054481089d
Create Date: 2025-08-31 13:19:51.331908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c69ae0cd521'
down_revision: Union[str, None] = '8f054481089d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new foreign key columns to students table
    op.add_column('students', sa.Column('teacher_id', sa.Integer(), nullable=True))
    op.add_column('students', sa.Column('case_manager_id', sa.Integer(), nullable=True))
    
    # Create foreign key constraints
    op.create_foreign_key(
        'fk_students_teacher_id', 
        'students', 
        'teachers', 
        ['teacher_id'], 
        ['id']
    )
    op.create_foreign_key(
        'fk_students_case_manager_id', 
        'students', 
        'teachers', 
        ['case_manager_id'], 
        ['id']
    )
    
    # Create indexes for better query performance
    op.create_index('ix_students_teacher_id', 'students', ['teacher_id'])
    op.create_index('ix_students_case_manager_id', 'students', ['case_manager_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_students_case_manager_id', 'students')
    op.drop_index('ix_students_teacher_id', 'students')
    
    # Remove foreign key constraints
    op.drop_constraint('fk_students_case_manager_id', 'students', type_='foreignkey')
    op.drop_constraint('fk_students_teacher_id', 'students', type_='foreignkey')
    
    # Remove columns
    op.drop_column('students', 'case_manager_id')
    op.drop_column('students', 'teacher_id')
