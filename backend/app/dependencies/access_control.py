from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import AuthContext, ensure_student_access
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.models.student_eligibility import StudentEligibility
from app.models.therapy_session import TherapySession
from app.models.appointment import Appointment


def ensure_goal_access(db: Session, auth: AuthContext, goal_id: int) -> IEPGoal:
    goal = db.query(IEPGoal).filter(IEPGoal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    ensure_student_access(auth, goal.student_id, action="goal access")
    return goal


def ensure_objective_access(db: Session, auth: AuthContext, objective_id: int) -> GoalObjective:
    objective = (
        db.query(GoalObjective)
        .join(IEPGoal, GoalObjective.goal_id == IEPGoal.id)
        .filter(GoalObjective.id == objective_id)
        .first()
    )
    if objective is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
    ensure_student_access(auth, objective.goal.student_id, action="objective access")
    return objective


def ensure_progress_entry_access(db: Session, auth: AuthContext, entry_id: int) -> ObjectiveProgressEntry:
    entry = (
        db.query(ObjectiveProgressEntry)
        .join(GoalObjective, ObjectiveProgressEntry.objective_id == GoalObjective.id)
        .join(IEPGoal, GoalObjective.goal_id == IEPGoal.id)
        .filter(ObjectiveProgressEntry.id == entry_id)
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress entry not found")
    ensure_student_access(auth, entry.objective.goal.student_id, action="progress entry access")
    return entry


def ensure_eligibility_access(db: Session, auth: AuthContext, eligibility_id: int) -> StudentEligibility:
    eligibility = db.query(StudentEligibility).filter(StudentEligibility.id == eligibility_id).first()
    if eligibility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student eligibility not found")
    ensure_student_access(auth, eligibility.student_id, action="eligibility access")
    return eligibility


def ensure_therapy_session_access(db: Session, auth: AuthContext, session_id: int) -> TherapySession:
    session = db.query(TherapySession).filter(TherapySession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Therapy session not found")
    ensure_student_access(auth, session.student_id, action="therapy session access")
    return session


def ensure_appointment_access(db: Session, auth: AuthContext, appointment_id: int) -> Appointment:
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    ensure_student_access(auth, appointment.student_id, action="appointment access")
    return appointment

