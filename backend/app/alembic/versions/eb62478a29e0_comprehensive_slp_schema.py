"""comprehensive_slp_schema

Revision ID: eb62478a29e0
Revises: d702babff7fb
Create Date: 2025-08-08 21:41:26.903724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.sqltypes import Numeric


# revision identifiers, used by Alembic.
revision: str = 'eb62478a29e0'
down_revision: Union[str, None] = 'd702babff7fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to existing students table
    op.add_column('students', sa.Column('uic', sa.String(50), nullable=True, unique=True, comment='Unique Identifier Code from legacy IEP system'))
    op.add_column('students', sa.Column('grade_level', sa.String(10), nullable=True))
    op.add_column('students', sa.Column('teacher_name', sa.String(100), nullable=True))
    op.add_column('students', sa.Column('enrollment_status', sa.String(20), nullable=False, server_default='Active'))
    op.add_column('students', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('students', sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')))
    op.add_column('students', sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')))
    
    # Rename existing columns to match schema requirements
    op.alter_column('students', 'first_name', new_column_name='first')
    op.alter_column('students', 'last_name', new_column_name='last')
    
    # Create indexes for students table
    op.create_index('ix_students_uic', 'students', ['uic'])
    op.create_index('ix_students_enrollment_status', 'students', ['enrollment_status'])
    op.create_index('ix_students_grade_level', 'students', ['grade_level'])
    
    # Create service_types lookup table
    op.create_table('service_types',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create goal_categories lookup table
    op.create_table('goal_categories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create assessment_types lookup table
    op.create_table('assessment_types',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create service_information table
    op.create_table('service_information',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('service_type_id', sa.Integer(), sa.ForeignKey('service_types.id'), nullable=False),
        sa.Column('frequency_per_week', sa.Integer(), nullable=True),
        sa.Column('session_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('service_location', sa.String(100), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create iep_goals table
    op.create_table('iep_goals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('goal_category_id', sa.Integer(), sa.ForeignKey('goal_categories.id'), nullable=False),
        sa.Column('goal_description', sa.Text(), nullable=False),
        sa.Column('target_behavior', sa.Text(), nullable=True),
        sa.Column('baseline_data', sa.String(500), nullable=True),
        sa.Column('target_criteria', sa.String(500), nullable=False),
        sa.Column('goal_status', sa.String(20), nullable=False, server_default='Active'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('mastery_date', sa.Date(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create progress_tracking table
    op.create_table('progress_tracking',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('goal_id', sa.Integer(), sa.ForeignKey('iep_goals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('data_collection_method', sa.String(100), nullable=True),
        sa.Column('performance_score', Numeric(5, 2), nullable=True),
        sa.Column('performance_percentage', Numeric(5, 2), nullable=True),
        sa.Column('trials_correct', sa.Integer(), nullable=True),
        sa.Column('trials_total', sa.Integer(), nullable=True),
        sa.Column('qualitative_notes', sa.Text(), nullable=True),
        sa.Column('session_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create assessment_data table
    op.create_table('assessment_data',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='NO ACTION'), nullable=False),
        sa.Column('assessment_type_id', sa.Integer(), sa.ForeignKey('assessment_types.id'), nullable=False),
        sa.Column('assessment_name', sa.String(200), nullable=False),
        sa.Column('assessment_date', sa.Date(), nullable=False),
        sa.Column('standard_score', sa.Integer(), nullable=True),
        sa.Column('percentile_rank', sa.Integer(), nullable=True),
        sa.Column('age_equivalent', sa.String(20), nullable=True),
        sa.Column('grade_equivalent', sa.String(20), nullable=True),
        sa.Column('raw_score', sa.Integer(), nullable=True),
        sa.Column('scaled_score', sa.Integer(), nullable=True),
        sa.Column('results_summary', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
    )
    
    # Create indexes for performance
    op.create_index('ix_service_information_student_id', 'service_information', ['student_id'])
    op.create_index('ix_service_information_service_type_id', 'service_information', ['service_type_id'])
    op.create_index('ix_service_information_start_date', 'service_information', ['start_date'])
    op.create_index('ix_service_information_is_active', 'service_information', ['is_active'])
    
    op.create_index('ix_iep_goals_student_id', 'iep_goals', ['student_id'])
    op.create_index('ix_iep_goals_goal_category_id', 'iep_goals', ['goal_category_id'])
    op.create_index('ix_iep_goals_goal_status', 'iep_goals', ['goal_status'])
    op.create_index('ix_iep_goals_start_date', 'iep_goals', ['start_date'])
    
    op.create_index('ix_progress_tracking_student_id', 'progress_tracking', ['student_id'])
    op.create_index('ix_progress_tracking_goal_id', 'progress_tracking', ['goal_id'])
    op.create_index('ix_progress_tracking_session_date', 'progress_tracking', ['session_date'])
    
    op.create_index('ix_assessment_data_student_id', 'assessment_data', ['student_id'])
    op.create_index('ix_assessment_data_assessment_type_id', 'assessment_data', ['assessment_type_id'])
    op.create_index('ix_assessment_data_assessment_date', 'assessment_data', ['assessment_date'])
    
    # Insert default lookup data
    op.execute("""
        INSERT INTO service_types (name, description) VALUES 
        ('Individual', 'One-on-one therapy sessions'),
        ('Group', 'Small group therapy sessions'),
        ('Consultation', 'Consultation with teachers/staff'),
        ('Assessment', 'Evaluation and assessment sessions'),
        ('IEP Meeting', 'IEP team meetings and planning')
    """)
    
    op.execute("""
        INSERT INTO goal_categories (name, description) VALUES 
        ('Articulation', 'Speech sound production goals'),
        ('Language', 'Receptive and expressive language goals'),
        ('Fluency', 'Stuttering and fluency goals'),
        ('Voice', 'Voice quality and vocal hygiene goals'),
        ('Pragmatics', 'Social communication and pragmatic language goals'),
        ('Feeding/Swallowing', 'Oral motor and swallowing goals'),
        ('Cognitive-Communication', 'Cognitive and executive function goals'),
        ('Augmentative Communication', 'AAC and assistive technology goals')
    """)
    
    op.execute("""
        INSERT INTO assessment_types (name, description) VALUES 
        ('Standardized', 'Norm-referenced standardized assessments'),
        ('Informal', 'Non-standardized observational assessments'),
        ('Screening', 'Brief screening tools'),
        ('Diagnostic', 'Comprehensive diagnostic evaluations'),
        ('Progress Monitoring', 'Ongoing progress monitoring tools'),
        ('Curriculum-Based', 'Curriculum-based assessments')
    """)


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('assessment_data')
    op.drop_table('progress_tracking')
    op.drop_table('iep_goals')
    op.drop_table('service_information')
    op.drop_table('assessment_types')
    op.drop_table('goal_categories')
    op.drop_table('service_types')
    
    # Remove indexes from students table
    op.drop_index('ix_students_grade_level', 'students')
    op.drop_index('ix_students_enrollment_status', 'students')
    op.drop_index('ix_students_uic', 'students')
    
    # Revert column name changes
    op.alter_column('students', 'first', new_column_name='first_name')
    op.alter_column('students', 'last', new_column_name='last_name')
    
    # Remove added columns from students table
    op.drop_column('students', 'modified_date')
    op.drop_column('students', 'created_date')
    op.drop_column('students', 'date_of_birth')
    op.drop_column('students', 'enrollment_status')
    op.drop_column('students', 'teacher_name')
    op.drop_column('students', 'grade_level')
    op.drop_column('students', 'uic')
