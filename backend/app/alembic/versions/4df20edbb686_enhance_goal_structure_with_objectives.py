"""enhance_goal_structure_with_objectives

Revision ID: 4df20edbb686
Revises: bdd0c65d76c7
Create Date: 2025-08-08 22:52:36.947191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4df20edbb686'
down_revision: Union[str, None] = 'bdd0c65d76c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add goal_number to iep_goals table
    op.add_column('iep_goals', sa.Column('goal_number', sa.String(20), nullable=True, comment='Goal number/identifier'))
    
    # Create goal_objectives table
    op.create_table('goal_objectives',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('goal_id', sa.Integer(), sa.ForeignKey('iep_goals.id'), nullable=False, index=True),
        sa.Column('objective_number', sa.Integer(), nullable=False, comment='Objective sequence number (1-4)'),
        sa.Column('objective_description', sa.Text(), nullable=False, comment='Detailed objective description'),
        sa.Column('progress_status', sa.String(50), nullable=True, comment='Current progress status'),
        sa.Column('schedule_frequency', sa.String(50), nullable=True, comment='Tracking schedule (e.g., monthly, weekly)'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        
        # Constraints
        sa.UniqueConstraint('goal_id', 'objective_number', name='uq_goal_objective'),
        sa.CheckConstraint('objective_number >= 1 AND objective_number <= 4', name='ck_objective_number_range')
    )
    
    # Create objective_progress_entries table for detailed progress tracking
    op.create_table('objective_progress_entries',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('objective_id', sa.Integer(), sa.ForeignKey('goal_objectives.id'), nullable=False, index=True),
        sa.Column('progress_date', sa.Date(), nullable=False, index=True, comment='Date of progress entry'),
        sa.Column('progress_on_objective', sa.String(100), nullable=True, comment='Progress measurement/status'),
        sa.Column('progress_comments', sa.Text(), nullable=True, comment='Detailed progress notes'),
        sa.Column('therapist_initials', sa.String(10), nullable=True, comment='Therapist/clinician initials'),
        sa.Column('session_type', sa.String(50), nullable=True, comment='Type of session (individual, group, etc.)'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()'))
    )
    
    # Create indexes for performance (FK indexes are auto-created)
    op.create_index('ix_goal_objectives_objective_number', 'goal_objectives', ['objective_number'])
    op.create_index('ix_iep_goals_goal_number', 'iep_goals', ['goal_number'])
    # Note: progress_date index will be created by column definition


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_iep_goals_goal_number', 'iep_goals')
    op.drop_index('ix_goal_objectives_objective_number', 'goal_objectives')
    
    # Drop tables
    op.drop_table('objective_progress_entries')
    op.drop_table('goal_objectives')
    
    # Remove column
    op.drop_column('iep_goals', 'goal_number')
