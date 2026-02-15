"""
SQLAlchemy Trigger Compatibility Fix
====================================

This file shows how to configure SQLAlchemy to work with SQL Server triggers
by disabling the implicit_returning feature that causes OUTPUT clause conflicts.

The issue: SQLAlchemy uses INSERT...OUTPUT to get generated IDs, but SQL Server
doesn't allow OUTPUT clauses on tables with triggers.

The solution: Set implicit_returning=False to disable this behavior.
"""

# SOLUTION 1: Engine-level configuration (affects all tables)
# Update your database.py engine creation:

from sqlalchemy import create_engine

# Original engine creation (with trigger conflicts):
# engine = create_engine(database_url, **engine_kwargs)

# FIXED engine creation (compatible with triggers):
engine = create_engine(
    database_url, 
    implicit_returning=False,  # This fixes the trigger conflict!
    **engine_kwargs
)

print("✅ Engine configured with implicit_returning=False for trigger compatibility")

# SOLUTION 2: Table-level configuration (for specific tables only)
# Update your model classes:

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TherapySession(Base):
    __tablename__ = "therapy_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_notes = Column(Text, nullable=True)
    # ... other columns ...
    
    # This makes only this table compatible with triggers:
    __table_args__ = {'implicit_returning': False}

class SessionObjective(Base):
    __tablename__ = "session_objectives"
    
    id = Column(Integer, primary_key=True, index=True)
    session_notes = Column(Text, nullable=True)
    # ... other columns ...
    
    # This makes only this table compatible with triggers:
    __table_args__ = {'implicit_returning': False}

print("✅ Models configured with implicit_returning=False for trigger compatibility")

# SOLUTION 3: Hybrid approach - keep triggers enabled with proper SQLAlchemy config
sql_to_enable_triggers = """
-- Re-enable the audit triggers after fixing SQLAlchemy configuration
ENABLE TRIGGER trg_session_objectives_audit_safe ON session_objectives;
ENABLE TRIGGER trg_therapy_sessions_audit_safe ON therapy_sessions;

PRINT 'Audit triggers re-enabled - should now work with fixed SQLAlchemy config!';
"""

print("🔧 After applying the SQLAlchemy fix, run the SQL above to re-enable triggers")
print("📚 This approach gives you the best of both worlds:")
print("   - Automatic audit logging via triggers")
print("   - Full compatibility with SQLAlchemy ORM")
