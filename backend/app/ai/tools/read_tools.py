from __future__ import annotations

from datetime import date, datetime
from typing import Any

from agents import function_tool
from sqlalchemy.orm import Session, selectinload, joinedload

from app.ai.privacy import StudentAliasContext, redact_student_name_from_value
from app.db.database import SessionLocal
from app.models.goal_objective import GoalObjective
from app.models.iep_goal import IEPGoal
from app.models.session_goal import SessionGoal
from app.models.session_objective import SessionObjective
from app.models.student import Student
from app.models.therapy_session import TherapySession
from app.models.ai_saved_progress_note import AISavedProgressNote


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_read_tools(*, db: Session, alias_ctx: StudentAliasContext, user_id: int) -> list[Any]:
    @function_tool
    def get_student_year_plan_context() -> dict[str, Any]:
        """
        Return student metadata + annual goals hierarchy for current-year planning context.
        """
        local_db = SessionLocal()
        try:
            student = local_db.query(Student).filter(Student.id == alias_ctx.student_id).first()
            if not student:
                return {"error": "Student not found", "student_alias": alias_ctx.alias}

            goals = (
                local_db.query(IEPGoal)
                .filter(IEPGoal.student_id == alias_ctx.student_id)
                .order_by(IEPGoal.created_date.desc())
                .all()
            )

            annual_goals = []
            for goal in goals:
                objectives = (
                    local_db.query(GoalObjective)
                    .filter(GoalObjective.goal_id == goal.id)
                    .order_by(GoalObjective.objective_number.asc())
                    .all()
                )
                annual_goals.append(
                    {
                        "goal_id": goal.id,
                        "goal_number": goal.goal_number,
                        "goal_category_id": goal.goal_category_id,
                        "goal_category": goal.goal_category.name if goal.goal_category else None,
                        "goal_description": goal.goal_description,
                        "target_behavior": goal.target_behavior,
                        "target_criteria": goal.target_criteria,
                        "goal_status": goal.goal_status,
                        "start_date": _iso(goal.start_date),
                        "end_date": _iso(goal.end_date),
                        "objectives": [
                            {
                                "objective_id": objective.id,
                                "objective_number": objective.objective_number,
                                "objective_description": objective.objective_description,
                                "progress_status": objective.progress_status,
                                "schedule_frequency": objective.schedule_frequency,
                            }
                            for objective in objectives
                        ],
                    }
                )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "student_meta": {
                    "grade_level": student.grade_level,
                    "enrollment_status": student.enrollment_status,
                    "iep_date": _iso(student.iep_date),
                    "annual_review_due_date": _iso(student.annual_review_due_date),
                    "reevaluation_due_date": _iso(student.reevaluation_due_date),
                },
                "hierarchy": {
                    "level_1": "annual_goals",
                    "level_2": "goal_objectives",
                    "notes": "Each annual goal can have multiple objectives.",
                },
                "annual_goals": annual_goals,
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_student_profile() -> dict[str, Any]:
        """
        Return basic student profile fields for the selected student.
        """
        local_db = SessionLocal()
        try:
            student = local_db.query(Student).filter(Student.id == alias_ctx.student_id).first()
            if not student:
                return {"error": "Student not found", "student_alias": alias_ctx.alias}

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": student.id,
                "grade_level": student.grade_level,
                "enrollment_status": student.enrollment_status,
                "iep_date": _iso(student.iep_date),
                "annual_review_due_date": _iso(student.annual_review_due_date),
                "reevaluation_due_date": _iso(student.reevaluation_due_date),
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_student_goals_and_objectives() -> dict[str, Any]:
        """
        Return annual-goal hierarchy for the selected student.
        """
        local_db = SessionLocal()
        try:
            goals = (
                local_db.query(IEPGoal)
                .filter(IEPGoal.student_id == alias_ctx.student_id)
                .order_by(IEPGoal.created_date.desc())
                .all()
            )

            goal_payload = []
            for goal in goals:
                objectives = (
                    local_db.query(GoalObjective)
                    .filter(GoalObjective.goal_id == goal.id)
                    .order_by(GoalObjective.objective_number.asc())
                    .all()
                )
                goal_payload.append(
                    {
                        "goal_id": goal.id,
                        "goal_number": goal.goal_number,
                        "goal_category_id": goal.goal_category_id,
                        "goal_category": goal.goal_category.name if goal.goal_category else None,
                        "goal_description": goal.goal_description,
                        "target_behavior": goal.target_behavior,
                        "target_criteria": goal.target_criteria,
                        "goal_status": goal.goal_status,
                        "start_date": _iso(goal.start_date),
                        "end_date": _iso(goal.end_date),
                        "objectives": [
                            {
                                "objective_id": objective.id,
                                "objective_number": objective.objective_number,
                                "objective_description": objective.objective_description,
                                "progress_status": objective.progress_status,
                                "schedule_frequency": objective.schedule_frequency,
                            }
                            for objective in objectives
                        ],
                    }
                )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "hierarchy": {
                    "level_1": "annual_goals",
                    "level_2": "goal_objectives",
                    "notes": "Each student has annual goals, and each goal contains one or more objectives.",
                },
                "annual_goals": goal_payload,
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_student_therapy_sessions(limit: int = 20) -> dict[str, Any]:
        """
        Return recent therapy sessions with session_objective data.
        """
        bounded_limit = min(max(limit, 1), 100)
        local_db = SessionLocal()
        try:
            sessions = (
                local_db.query(TherapySession)
                .options(
                    selectinload(TherapySession.session_objectives).joinedload(SessionObjective.objective),
                    selectinload(TherapySession.session_objectives).joinedload(SessionObjective.goal),
                )
                .filter(TherapySession.student_id == alias_ctx.student_id)
                .order_by(TherapySession.session_date.desc())
                .limit(bounded_limit)
                .all()
            )

            session_payload = []
            for session in sessions:
                session_payload.append(
                    {
                        "therapy_session_id": session.id,
                        "session_date": _iso(session.session_date),
                        "status": session.status,
                        "session_type": session.session_type,
                        "planned_duration_minutes": session.planned_duration_minutes,
                        "actual_duration_minutes": session.actual_duration_minutes,
                        "session_notes": session.session_notes,
                        "therapist_observations": session.therapist_observations,
                        "student_engagement": session.student_engagement,
                        "goals_addressed": session.goals_addressed,
                        "session_quality": session.session_quality,
                        "follow_up_needed": session.follow_up_needed,
                        "follow_up_notes": session.follow_up_notes,
                        "session_objectives": [
                            {
                                "session_objective_id": obj.id,
                                "objective_id": obj.objective_id,
                                "objective_number": obj.objective.objective_number if obj.objective else None,
                                "objective_description": obj.objective.objective_description if obj.objective else None,
                                "goal_id": obj.goal_id,
                                "goal_number": obj.goal.goal_number if obj.goal else None,
                                "planned": obj.planned,
                                "worked_on": obj.worked_on,
                                "pre_session_notes": obj.pre_session_notes,
                                "session_notes": obj.session_notes,
                                "trials_attempted": obj.trials_attempted,
                                "trials_correct": obj.trials_correct,
                                "accuracy_percentage": float(obj.accuracy_percentage) if obj.accuracy_percentage is not None else None,
                                "independence_level": obj.independence_level,
                                "objective_met": obj.objective_met,
                                "progress_rating": obj.progress_rating,
                                "prompt_level": obj.prompt_level,
                                "time_spent_minutes": obj.time_spent_minutes,
                                "student_engagement": obj.student_engagement,
                            }
                            for obj in (session.session_objectives or [])
                        ],
                    }
                )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "therapy_sessions": session_payload,
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_student_therapy_dataset() -> dict[str, Any]:
        """
        Return full therapy dataset for student with session->goal/objective joins.

        This tool is designed for progress-note evaluation across all sessions.
        """
        local_db = SessionLocal()
        try:
            sessions = (
                local_db.query(TherapySession)
                .options(
                    selectinload(TherapySession.session_goals)
                    .joinedload(SessionGoal.goal)
                    .joinedload(IEPGoal.goal_category),
                    selectinload(TherapySession.session_objectives).joinedload(SessionObjective.objective),
                    selectinload(TherapySession.session_objectives)
                    .joinedload(SessionObjective.goal)
                    .joinedload(IEPGoal.goal_category),
                )
                .filter(TherapySession.student_id == alias_ctx.student_id)
                .order_by(TherapySession.session_date.asc())
                .all()
            )

            therapy_sessions = []
            for session in sessions:
                has_objective_data = any(
                    [
                        obj.session_notes,
                        obj.trials_attempted is not None,
                        obj.trials_correct is not None,
                        obj.accuracy_percentage is not None,
                        obj.progress_rating,
                        obj.objective_met is not None,
                        obj.worked_on,
                    ]
                    for obj in (session.session_objectives or [])
                )
                session_interpretation = (
                    "completed_session"
                    if session.status == "completed"
                    else "planned_not_completed_or_absent"
                )

                therapy_sessions.append(
                    {
                        "session_record": {
                            "id": session.id,
                            "student_id": session.student_id,
                            "session_date": _iso(session.session_date),
                            "start_time": _iso(session.start_time),
                            "end_time": _iso(session.end_time),
                            "planned_duration_minutes": session.planned_duration_minutes,
                            "session_type": session.session_type,
                            "status": session.status,
                            "status_interpretation": session_interpretation,
                            "has_objective_data": has_objective_data,
                        },
                        "session_goals": [
                            {
                                "id": sg.id,
                                "therapy_session_id": sg.therapy_session_id,
                                "goal_id": sg.goal_id,
                                "goal_number": sg.goal.goal_number if sg.goal else None,
                                "goal_category": sg.goal.goal_category.name if sg.goal and sg.goal.goal_category else None,
                                "goal_description": sg.goal.goal_description if sg.goal else None,
                            }
                            for sg in (session.session_goals or [])
                        ],
                        "session_objectives": [
                            {
                                "id": so.id,
                                "therapy_session_id": so.therapy_session_id,
                                "objective_id": so.objective_id,
                                "goal_id": so.goal_id,
                                "goal_number": so.goal.goal_number if so.goal else None,
                                "goal_category": so.goal.goal_category.name if so.goal and so.goal.goal_category else None,
                                "objective_number": so.objective.objective_number if so.objective else None,
                                "objective_description": so.objective.objective_description if so.objective else None,
                                "planned": so.planned,
                                "worked_on": so.worked_on,
                                "priority": so.priority,
                                "pre_session_notes": so.pre_session_notes,
                                "session_notes": so.session_notes,
                                "trials_attempted": so.trials_attempted,
                                "trials_correct": so.trials_correct,
                                "accuracy_percentage": float(so.accuracy_percentage) if so.accuracy_percentage is not None else None,
                                "independence_level": so.independence_level,
                                "objective_met": so.objective_met,
                                "progress_rating": so.progress_rating,
                                "prompt_level": so.prompt_level,
                                "time_spent_minutes": so.time_spent_minutes,
                                "student_engagement": so.student_engagement,
                                "data_collection_method": so.data_collection_method,
                                "created_date": _iso(so.created_date),
                                "modified_date": _iso(so.modified_date),
                            }
                            for so in (session.session_objectives or [])
                        ],
                    }
                )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "therapy_sessions": therapy_sessions,
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_student_progress_snapshot(limit: int = 50) -> dict[str, Any]:
        """
        Return current therapy objective history from active therapy workflow.
        """
        bounded_limit = min(max(limit, 1), 200)
        local_db = SessionLocal()
        try:
            current_therapy_entries = (
                local_db.query(SessionObjective)
                .join(TherapySession, SessionObjective.therapy_session_id == TherapySession.id)
                .options(joinedload(SessionObjective.objective), joinedload(SessionObjective.goal))
                .filter(
                    TherapySession.student_id == alias_ctx.student_id,
                    SessionObjective.worked_on == True,
                )
                .order_by(TherapySession.session_date.desc())
                .limit(bounded_limit)
                .all()
            )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "usage_notes": {
                    "current_data_source": "current_therapy_objective_history from session_objectives",
                    "legacy_objective_progress_entries_included": False,
                    "legacy_note": "Legacy objective_progress_entries are intentionally excluded for current testing.",
                },
                "current_therapy_objective_history": [
                    {
                        "session_objective_id": item.id,
                        "therapy_session_id": item.therapy_session_id,
                        "objective_id": item.objective_id,
                        "objective_number": item.objective.objective_number if item.objective else None,
                        "objective_description": item.objective.objective_description if item.objective else None,
                        "goal_id": item.goal_id,
                        "goal_number": item.goal.goal_number if item.goal else None,
                        "worked_on": item.worked_on,
                        "accuracy_percentage": float(item.accuracy_percentage) if item.accuracy_percentage is not None else None,
                        "independence_level": item.independence_level,
                        "objective_met": item.objective_met,
                        "progress_rating": item.progress_rating,
                        "prompt_level": item.prompt_level,
                        "time_spent_minutes": item.time_spent_minutes,
                        "session_notes": item.session_notes,
                        "pre_session_notes": item.pre_session_notes,
                    }
                    for item in current_therapy_entries
                ],
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    @function_tool
    def get_prior_saved_progress_notes(limit: int = 10) -> dict[str, Any]:
        """
        Return prior AI-saved progress notes for this student.
        """
        bounded_limit = min(max(limit, 1), 50)
        local_db = SessionLocal()
        try:
            notes = (
                local_db.query(AISavedProgressNote)
                .filter(
                    AISavedProgressNote.student_id == alias_ctx.student_id,
                    AISavedProgressNote.user_id == user_id,
                )
                .order_by(AISavedProgressNote.created_date.desc())
                .limit(bounded_limit)
                .all()
            )

            payload = {
                "student_alias": alias_ctx.alias,
                "student_id": alias_ctx.student_id,
                "saved_progress_notes": [
                    {
                        "saved_progress_note_id": note.id,
                        "title": note.title,
                        "note_content": note.note_content,
                        "template_version": note.template_version,
                        "status": note.status,
                        "created_date": _iso(note.created_date),
                    }
                    for note in notes
                ],
            }
            return redact_student_name_from_value(payload, alias_ctx)
        finally:
            local_db.close()

    return [
        get_student_year_plan_context,
        get_student_profile,
        get_student_goals_and_objectives,
        get_student_therapy_sessions,
        get_student_therapy_dataset,
        get_student_progress_snapshot,
        get_prior_saved_progress_notes,
    ]

