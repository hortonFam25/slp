"""add_iep_dates_to_students

Revision ID: bdd0c65d76c7
Revises: 1908d65cdefd
Create Date: 2025-08-08 22:42:35.064193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdd0c65d76c7'
down_revision: Union[str, None] = '1908d65cdefd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add IEP date fields to students table
    op.add_column('students', sa.Column('iep_date', sa.Date(), nullable=True, comment='Current IEP date'))
    op.add_column('students', sa.Column('annual_review_due_date', sa.Date(), nullable=True, comment='Annual IEP review due date'))
    op.add_column('students', sa.Column('reevaluation_due_date', sa.Date(), nullable=True, comment='Re-evaluation due date (every 3 years)'))
    op.add_column('students', sa.Column('iep_meeting_date', sa.Date(), nullable=True, comment='Last IEP meeting date'))
    op.add_column('students', sa.Column('initial_evaluation_date', sa.Date(), nullable=True, comment='Initial evaluation date'))
    op.add_column('students', sa.Column('eligibility_determination_date', sa.Date(), nullable=True, comment='Date eligibility was determined'))
    
    # Create indexes for IEP dates (for compliance tracking and reporting)
    op.create_index('ix_students_iep_date', 'students', ['iep_date'])
    op.create_index('ix_students_annual_review_due_date', 'students', ['annual_review_due_date'])
    op.create_index('ix_students_reevaluation_due_date', 'students', ['reevaluation_due_date'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_students_reevaluation_due_date', 'students')
    op.drop_index('ix_students_annual_review_due_date', 'students')
    op.drop_index('ix_students_iep_date', 'students')
    
    # Remove columns
    op.drop_column('students', 'eligibility_determination_date')
    op.drop_column('students', 'initial_evaluation_date')
    op.drop_column('students', 'iep_meeting_date')
    op.drop_column('students', 'reevaluation_due_date')
    op.drop_column('students', 'annual_review_due_date')
    op.drop_column('students', 'iep_date')
