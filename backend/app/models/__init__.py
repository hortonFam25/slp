from app.models.student import Student  # noqa: F401
from app.models.service_type import ServiceType  # noqa: F401
from app.models.goal_category import GoalCategory  # noqa: F401
from app.models.assessment_type import AssessmentType  # noqa: F401
from app.models.service_information import ServiceInformation  # noqa: F401
from app.models.iep_goal import IEPGoal  # noqa: F401
from app.models.goal_objective import GoalObjective  # noqa: F401
from app.models.objective_progress_entry import ObjectiveProgressEntry  # noqa: F401
from app.models.progress_tracking import ProgressTracking  # noqa: F401
from app.models.assessment_data import AssessmentData  # noqa: F401
from app.models.eligibility_category import EligibilityCategory  # noqa: F401
from app.models.student_eligibility import StudentEligibility  # noqa: F401
from app.models.school import School  # noqa: F401
from app.models.teacher import Teacher  # noqa: F401
from app.models.teacher_school_assignment import TeacherSchoolAssignment  # noqa: F401
from app.models.student_teacher_assignment import StudentTeacherAssignment  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.time_block import TimeBlock  # noqa: F401
from app.models.time_block_activity import TimeBlockActivity  # noqa: F401
from app.models.activity_student_assignment import ActivityStudentAssignment  # noqa: F401
from app.models.block_assignment import BlockAssignment  # noqa: F401
from app.models.therapy_session import TherapySession  # noqa: F401
from app.models.session_goal import SessionGoal  # noqa: F401
from app.models.session_objective import SessionObjective  # noqa: F401
# Written by SQL Server triggers, never by the app — registered so the table
# is schema-managed rather than hand-made. See the module docstring.
from app.models.therapy_session_audit_log import TherapySessionAuditLog  # noqa: F401
from app.models.ai_chat_session import AIChatSession  # noqa: F401
from app.models.ai_chat_message import AIChatMessage  # noqa: F401
from app.models.ai_saved_progress_note import AISavedProgressNote  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_student_access import UserStudentAccess  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.teacher_role import TeacherRole  # noqa: F401


from app.models.api_token import ApiToken  # noqa: F401

# The OAuth facade's own tables. Imported after ApiToken because api_tokens
# carries the (later-added) FK columns that point back at these.
from app.models.oauth_client import OAuthClient  # noqa: F401
from app.models.oauth_code import OAuthCode  # noqa: F401
from app.models.oauth_refresh_token import OAuthRefreshToken  # noqa: F401
