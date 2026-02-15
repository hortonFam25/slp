"""create_schools_and_teachers_tables

Revision ID: bd8de57a27e2
Revises: 8d2fc1498eae
Create Date: 2025-08-09 00:00:20.955369

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd8de57a27e2'
down_revision: Union[str, None] = '8d2fc1498eae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schools table
    op.create_table('schools',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(200), nullable=False, index=True, comment='School name'),
        sa.Column('address', sa.String(500), nullable=True, comment='School address'),
        sa.Column('phone', sa.String(20), nullable=True, comment='School phone number'),
        sa.Column('email', sa.String(100), nullable=True, comment='School email address'),
        sa.Column('district', sa.String(100), nullable=True, comment='School district'),
        sa.Column('principal_name', sa.String(100), nullable=True, comment='Principal name'),
        sa.Column('contact_person', sa.String(100), nullable=True, comment='Primary contact person'),
        sa.Column('contact_phone', sa.String(20), nullable=True, comment='Contact person phone'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Additional notes about the school'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1', comment='Whether school is active'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()'))
    )
    
    # Create teachers table
    op.create_table('teachers',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('first_name', sa.String(100), nullable=False, comment='Teacher first name'),
        sa.Column('last_name', sa.String(100), nullable=False, comment='Teacher last name'),
        sa.Column('email', sa.String(100), nullable=True, index=True, comment='Teacher email'),
        sa.Column('phone', sa.String(20), nullable=True, comment='Teacher phone number'),
        sa.Column('title', sa.String(100), nullable=True, comment='Teacher title/position'),
        sa.Column('department', sa.String(100), nullable=True, comment='Department or subject area'),
        sa.Column('room_number', sa.String(20), nullable=True, comment='Classroom or office room number'),
        sa.Column('preferred_contact_method', sa.String(20), nullable=True, comment='Preferred contact method'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Additional notes about the teacher'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1', comment='Whether teacher is active'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()'))
    )
    
    # Create teacher-school assignments table (many-to-many)
    op.create_table('teacher_school_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False, index=True),
        sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=False, index=True),
        sa.Column('start_date', sa.Date(), nullable=False, comment='Assignment start date'),
        sa.Column('end_date', sa.Date(), nullable=True, comment='Assignment end date (null if current)'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='0', comment='Is this the teachers primary school'),
        sa.Column('notes', sa.String(500), nullable=True, comment='Assignment notes'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.UniqueConstraint('teacher_id', 'school_id', 'start_date', name='uq_teacher_school_assignment')
    )
    
    # Create student-teacher assignments table (many-to-many)
    op.create_table('student_teacher_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False, index=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False, index=True),
        sa.Column('subject', sa.String(100), nullable=True, comment='Subject or class'),
        sa.Column('start_date', sa.Date(), nullable=False, comment='Assignment start date'),
        sa.Column('end_date', sa.Date(), nullable=True, comment='Assignment end date (null if current)'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='0', comment='Is this the students primary teacher'),
        sa.Column('notes', sa.String(500), nullable=True, comment='Assignment notes'),
        sa.Column('created_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.Column('modified_date', sa.DateTime(), nullable=False, server_default=sa.text('GETDATE()')),
        sa.UniqueConstraint('student_id', 'teacher_id', 'subject', 'start_date', name='uq_student_teacher_assignment')
    )
    
    # Add school_id to students table (many students can be at one school)
    op.add_column('students', sa.Column('school_id', sa.Integer(), sa.ForeignKey('schools.id'), nullable=True, index=True, comment='Students current school'))
    
    # Create indexes for performance
    op.create_index('ix_schools_name', 'schools', ['name'])
    op.create_index('ix_schools_district', 'schools', ['district'])
    op.create_index('ix_teachers_last_name', 'teachers', ['last_name'])
    op.create_index('ix_teachers_first_name', 'teachers', ['first_name'])
    op.create_index('ix_teacher_school_assignments_start_date', 'teacher_school_assignments', ['start_date'])
    op.create_index('ix_student_teacher_assignments_start_date', 'student_teacher_assignments', ['start_date'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_student_teacher_assignments_start_date', 'student_teacher_assignments')
    op.drop_index('ix_teacher_school_assignments_start_date', 'teacher_school_assignments')
    op.drop_index('ix_teachers_first_name', 'teachers')
    op.drop_index('ix_teachers_last_name', 'teachers')
    op.drop_index('ix_schools_district', 'schools')
    op.drop_index('ix_schools_name', 'schools')
    
    # Remove foreign key column from students
    op.drop_column('students', 'school_id')
    
    # Drop tables in reverse order (relationships first)
    op.drop_table('student_teacher_assignments')
    op.drop_table('teacher_school_assignments')
    op.drop_table('teachers')
    op.drop_table('schools')
