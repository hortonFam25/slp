import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.models.student import Student
from app.models.iep_goal import IEPGoal
from app.models.goal_objective import GoalObjective
from app.models.objective_progress_entry import ObjectiveProgressEntry
from app.models.goal_category import GoalCategory
from app.repositories.student_repository import StudentRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.goal_category_repository import GoalCategoryRepository
from app.schemas.goals_import import (
    GoalImportRow, GoalsImportResult, parse_goals_csv_content, 
    convert_legacy_csv_to_goal_import
)
from app.schemas.iep_goal import IEPGoalCreate
from app.schemas.goal_objective import GoalObjectiveCreate

logger = logging.getLogger(__name__)


class GoalsImportService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.student_repo = StudentRepository(db_session)
        self.goal_repo = GoalRepository(db_session)
        self.goal_category_repo = GoalCategoryRepository(db_session)
    
    def import_goals_from_csv(
        self, 
        csv_content: str, 
        skip_duplicates: bool = True,
        update_existing: bool = False,
        default_goal_category: str = "Speech/Language"
    ) -> GoalsImportResult:
        """
        Import goals and objectives from CSV content
        
        Args:
            csv_content: Raw CSV file content
            skip_duplicates: Skip goals for students that already have active goals
            update_existing: Update existing goals when found
            default_goal_category: Default goal category to use
        """
        
        # Parse CSV content
        try:
            raw_rows = parse_goals_csv_content(csv_content)
        except ValueError as e:
            return GoalsImportResult(
                total_rows=0,
                successful_imports=0,
                failed_imports=1,
                skipped_duplicates=0,
                updated_existing=0,
                goals_created=0,
                objectives_created=0,
                progress_entries_created=0,
                errors=[{"row": 0, "error": str(e)}],
                imported_goals=[]
            )
        
        result = GoalsImportResult(
            total_rows=len(raw_rows),
            successful_imports=0,
            failed_imports=0,
            skipped_duplicates=0,
            updated_existing=0,
            goals_created=0,
            objectives_created=0,
            progress_entries_created=0,
            errors=[],
            imported_goals=[]
        )
        
        # Get or create default goal category
        goal_category = self._get_or_create_goal_category(default_goal_category)
        
        # Process in batches to improve performance
        batch_size = 10
        processed_count = 0
        
        for raw_row in raw_rows:
            processed_count += 1
            try:
                row_number = raw_row.pop('_row_number', 0)
                
                # Convert legacy CSV format to our import format
                goal_import_data = convert_legacy_csv_to_goal_import(raw_row)
                
                # Find student by UIC
                student = self.student_repo.get_student_by_uic(goal_import_data.student_uic)
                if not student:
                    result.failed_imports += 1
                    result.errors.append({
                        "row": row_number,
                        "error": f"Student with UIC '{goal_import_data.student_uic}' not found",
                        "data": raw_row
                    })
                    continue

                # An ARCHIVED student is not an importable one. The UIC lookup
                # above deliberately sees the archive (`students.uic` is UNIQUE
                # and the archived row still owns it -- see
                # `StudentRepository`), so this is the only place the archive
                # can be honoured. Writing the goal anyway would hang an ACTIVE
                # row off a hidden parent: invisible to every list, counted by
                # no total, and precisely the orphan `archive.restore` refuses
                # to create. The therapist has to restore the student first.
                if student.archived_at is not None:
                    result.failed_imports += 1
                    result.errors.append({
                        "row": row_number,
                        "error": (
                            f"Student with UIC '{goal_import_data.student_uic}' "
                            f"is ARCHIVED, not absent. Restore that student "
                            f"before importing goals for them."
                        ),
                        "data": raw_row
                    })
                    continue
                
                # Check for existing goals
                existing_goals = self.goal_repo.get_goals(student_id=student.id, goal_status="Active")
                
                if existing_goals and skip_duplicates and not update_existing:
                    result.skipped_duplicates += 1
                    continue
                
                # Create or update goal
                if existing_goals and update_existing:
                    # Update existing goal (for now, we'll add a new goal - could be enhanced to truly update)
                    goal = self._create_goal_with_objectives(
                        student, goal_import_data, goal_category, row_number
                    )
                    result.updated_existing += 1
                else:
                    # Create new goal
                    goal = self._create_goal_with_objectives(
                        student, goal_import_data, goal_category, row_number
                    )
                    result.goals_created += 1
                
                if goal:
                    result.successful_imports += 1
                    result.objectives_created += len(goal.objectives)
                    
                    # Count progress entries created
                    for objective in goal.objectives:
                        result.progress_entries_created += len(objective.progress_entries)
                    
                    result.imported_goals.append({
                        "goal_id": goal.id,
                        "student_name": f"{student.first} {student.last}",
                        "student_uic": student.uic,
                        "goal_description": goal.goal_description[:100] + "..." if len(goal.goal_description) > 100 else goal.goal_description,
                        "objectives_count": len(goal.objectives),
                        "action": "updated" if existing_goals and update_existing else "created"
                    })
                
            except Exception as e:
                result.failed_imports += 1
                result.errors.append({
                    "row": row_number,
                    "error": str(e),
                    "data": raw_row
                })
            
            # Commit in batches for better performance
            if processed_count % batch_size == 0:
                try:
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    logger.exception("Batch commit error at row %s", processed_count)
        
        # Final commit for any remaining items
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.exception("Final commit error")
        
        return result
    
    def _get_or_create_goal_category(self, category_name: str) -> GoalCategory:
        """Get existing goal category or create new one"""
        try:
            # Try to find existing category
            categories = self.goal_category_repo.get_all_categories(active_only=True)
            for category in categories:
                if category.name.lower() == category_name.lower():
                    return category
            
            # Create new category if not found
            from app.schemas.goal_category import GoalCategoryCreate
            new_category_data = GoalCategoryCreate(
                name=category_name,
                description=f"Auto-created category for CSV import: {category_name}",
                is_active=True
            )
            return self.goal_category_repo.create_category(new_category_data)
            
        except Exception as e:
            # If we can't create/find category, return a default one or None
            logger.warning("Could not get/create goal category %r: %s", category_name, e)
            # Try to get the first available category
            try:
                categories = self.goal_category_repo.get_all_categories(active_only=True)
                if categories:
                    return categories[0]
            except:
                pass
            return None
    
    def _create_goal_with_objectives(
        self, 
        student: Student, 
        goal_data: GoalImportRow, 
        goal_category: GoalCategory,
        row_number: int
    ) -> Optional[IEPGoal]:
        """Create a goal with its objectives and progress entries"""
        
        try:
            # Determine start date
            start_date = date.today()
            if goal_data.start_date:
                start_date = date.fromisoformat(goal_data.start_date)
            
            # Determine end date (default to 1 year from start)
            end_date = None
            if goal_data.end_date:
                end_date = date.fromisoformat(goal_data.end_date)
            else:
                # Default to 1 year from start date
                end_date = date(start_date.year + 1, start_date.month, start_date.day)
            
            # Create goal
            goal_create_data = IEPGoalCreate(
                student_id=student.id,
                goal_category_id=goal_category.id if goal_category else 1,  # Fallback to ID 1
                goal_description=goal_data.goal_description,
                target_criteria=goal_data.target_criteria or "80% accuracy over 3 consecutive sessions",
                goal_status="Active",
                start_date=start_date,
                end_date=end_date,
                baseline_data=f"Imported from legacy system - Staff: {goal_data.responsible_staff}" if goal_data.responsible_staff else None
            )
            
            created_goal = self.goal_repo.create_goal(goal_create_data)
            
            # Create objectives and progress entries
            for i, objective_data in enumerate(goal_data.objectives, 1):
                # Create objective
                objective_create_data = GoalObjectiveCreate(
                    goal_id=created_goal.id,
                    objective_number=i,
                    objective_description=objective_data.objective_description,
                    schedule_frequency=objective_data.schedule_frequency
                )
                
                # Use direct SQL to create objective since we might not have a dedicated repository
                objective = GoalObjective(
                    goal_id=created_goal.id,
                    objective_number=i,
                    objective_description=objective_data.objective_description,
                    schedule_frequency=objective_data.schedule_frequency
                )
                self.db.add(objective)
                self.db.flush()  # Get the ID for progress entries
                
                # Create progress entry if we have progress data
                if objective_data.progress_comments or objective_data.progress_date:
                    progress_date = date.today()
                    if objective_data.progress_date:
                        progress_date = date.fromisoformat(objective_data.progress_date)
                    
                    progress_entry = ObjectiveProgressEntry(
                        objective_id=objective.id,
                        progress_date=progress_date,
                        progress_comments=objective_data.progress_comments,
                        therapist_initials=goal_data.responsible_staff[:10] if goal_data.responsible_staff else None,
                        session_type="Legacy Import"
                    )
                    self.db.add(progress_entry)
            
            # Flush to get IDs but don't commit yet (batch commits handled in main loop)
            self.db.flush()
            
            # Refresh to get all relationships
            self.db.refresh(created_goal)
            return created_goal
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create goal: {str(e)}")
    
    def validate_goals_csv_preview(self, csv_content: str, max_preview_rows: int = 10) -> Dict[str, Any]:
        """
        Validate goals CSV and return preview of what would be imported
        """
        try:
            raw_rows = parse_goals_csv_content(csv_content)
        except ValueError as e:
            return {
                "valid": False,
                "error": str(e),
                "preview_rows": []
            }
        
        preview_rows = []
        validation_errors = []
        
        for i, raw_row in enumerate(raw_rows[:max_preview_rows]):
            try:
                row_number = raw_row.pop('_row_number', i + 2)
                goal_import_data = convert_legacy_csv_to_goal_import(raw_row)
                
                # Check if student exists
                student = self.student_repo.get_student_by_uic(goal_import_data.student_uic)
                existing_goals = []
                if student:
                    existing_goals = self.goal_repo.get_goals(student_id=student.id, goal_status="Active")
                
                preview_rows.append({
                    "row_number": row_number,
                    "data": {
                        "student_uic": goal_import_data.student_uic,
                        "student_name": f"{student.first} {student.last}" if student else "NOT FOUND",
                        "goal_description": goal_import_data.goal_description[:100] + "..." if len(goal_import_data.goal_description) > 100 else goal_import_data.goal_description,
                        "objectives_count": len(goal_import_data.objectives),
                        "responsible_staff": goal_import_data.responsible_staff,
                        "has_progress_data": any(obj.progress_comments or obj.progress_date for obj in goal_import_data.objectives)
                    },
                    "status": "update" if (student and existing_goals) else "create" if student else "error",
                    "existing_goals_count": len(existing_goals) if existing_goals else 0,
                    "valid": student is not None
                })
                
            except Exception as e:
                validation_errors.append({
                    "row": i + 2,
                    "error": str(e),
                    "data": raw_row
                })
                
                preview_rows.append({
                    "row_number": i + 2,
                    "data": raw_row,
                    "status": "error",
                    "error": str(e),
                    "valid": False
                })
        
        return {
            "valid": len(validation_errors) == 0,
            "total_rows": len(raw_rows),
            "preview_rows": preview_rows,
            "validation_errors": validation_errors,
            "has_more_rows": len(raw_rows) > max_preview_rows
        }
