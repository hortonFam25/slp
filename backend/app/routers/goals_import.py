from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.services.goals_import_service import GoalsImportService
from app.schemas.goals_import import GoalsImportRequest, GoalsImportResult, generate_goals_csv_template


router = APIRouter(prefix="/api/goals-csv", tags=["goals-csv-import"])


@router.get("/template")
def download_goals_csv_template():
    """Download a CSV template for goals and objectives import"""
    
    template_content = generate_goals_csv_template()
    
    # Create a streaming response
    def generate_csv():
        yield template_content
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=goals_objectives_template.csv"}
    )


@router.post("/preview", response_model=dict)
def preview_goals_csv_import(
    file: UploadFile = File(...),
    max_rows: int = Query(10, ge=1, le=50, description="Maximum rows to preview"),
    db: Session = Depends(get_db)
):
    """
    Preview goals CSV import - validate and show what would be imported
    """
    
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    try:
        # Read file content
        content = file.file.read()
        
        # Try multiple encodings to handle different CSV exports
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1', 'latin-1']
        csv_content = None
        
        for encoding in encodings:
            try:
                csv_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if csv_content is None:
            raise UnicodeDecodeError("Could not decode file with any supported encoding")
        
        # Create import service
        import_service = GoalsImportService(db)
        
        # Validate and preview
        preview_result = import_service.validate_goals_csv_preview(csv_content, max_rows)
        
        return {
            "filename": file.filename,
            "file_size": len(content),
            **preview_result
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@router.post("/import", response_model=GoalsImportResult)
def import_goals_csv(
    file: UploadFile = File(...),
    skip_duplicates: bool = Query(True, description="Skip goals for students that already have active goals"),
    update_existing: bool = Query(False, description="Update existing goals if student already has goals"),
    default_goal_category: str = Query("Speech/Language", description="Default goal category"),
    db: Session = Depends(get_db)
):
    """
    Import goals and objectives from CSV file
    """
    
    # Validate file type
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    try:
        # Read file content
        content = file.file.read()
        
        # Try multiple encodings to handle different CSV exports
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1', 'latin-1']
        csv_content = None
        
        for encoding in encodings:
            try:
                csv_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if csv_content is None:
            raise UnicodeDecodeError("Could not decode file with any supported encoding")
        
        # Create import service
        import_service = GoalsImportService(db)
        
        # Import goals
        result = import_service.import_goals_from_csv(
            csv_content=csv_content,
            skip_duplicates=skip_duplicates,
            update_existing=update_existing,
            default_goal_category=default_goal_category
        )
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing goals: {str(e)}")


@router.post("/import-text", response_model=GoalsImportResult)
def import_goals_csv_text(
    request: GoalsImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import goals and objectives from CSV text content (alternative to file upload)
    """
    
    try:
        # Create import service
        import_service = GoalsImportService(db)
        
        # Import goals
        result = import_service.import_goals_from_csv(
            csv_content=request.file_content,
            skip_duplicates=request.skip_duplicates,
            update_existing=request.update_existing,
            default_goal_category=request.default_goal_category
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing goals: {str(e)}")


@router.get("/export")
def export_goals_csv(
    student_uic: Optional[str] = Query(None, description="Filter by student UIC"),
    goal_category: Optional[str] = Query(None, description="Filter by goal category"),
    db: Session = Depends(get_db)
):
    """
    Export existing goals and objectives to CSV format
    """
    
    try:
        from app.repositories.goal_repository import GoalRepository
        from app.repositories.student_repository import StudentRepository
        import csv
        from io import StringIO
        
        goal_repo = GoalRepository(db)
        student_repo = StudentRepository(db)
        
        # Get goals based on filters
        if student_uic:
            student = student_repo.get_student_by_uic(student_uic)
            if not student:
                raise HTTPException(status_code=404, detail=f"Student with UIC '{student_uic}' not found")
            goals = goal_repo.get_goals_by_student(student.id)
        else:
            # Get all goals (this might need pagination for large datasets)
            goals = goal_repo.list_goals(active_only=True)
        
        # Generate CSV content
        output = StringIO()
        fieldnames = [
            'ID', 'Goal', 'Responsible Staff',
            'Objective1', 'Schedule1', 'Prog Comments 1', 'prog Date1',
            'Objective2', 'Schedule2', 'Prog Comments 2', 'prog Date2',
            'Objective3', 'Schedule3', 'Prog Comments 3', 'prog Date3',
            'Objective4', 'Schedule4', 'Prog Comments 4', 'prog Date4',
            'Objective5', 'Schedule5', 'Prog Comments 5', 'prog Date5'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for goal in goals:
            row_data = {
                'ID': goal.student.uic or str(goal.student.id),
                'Goal': goal.goal_description,
                'Responsible Staff': 'Speech Pathologist'  # Default value
            }
            
            # Add objectives (up to 5)
            objectives = sorted(goal.objectives, key=lambda x: x.objective_number)[:5]
            for i, objective in enumerate(objectives, 1):
                latest_progress = objective.latest_progress_entry
                
                row_data[f'Objective{i}'] = objective.objective_description
                row_data[f'Schedule{i}'] = objective.schedule_frequency or ''
                row_data[f'Prog Comments {i}'] = latest_progress.progress_comments if latest_progress else ''
                row_data[f'prog Date{i}'] = latest_progress.progress_date.strftime('%m/%d/%Y') if latest_progress and latest_progress.progress_date else ''
            
            # Fill empty objective slots
            for i in range(len(objectives) + 1, 6):
                row_data[f'Objective{i}'] = ''
                row_data[f'Schedule{i}'] = ''
                row_data[f'Prog Comments {i}'] = ''
                row_data[f'prog Date{i}'] = ''
            
            writer.writerow(row_data)
        
        csv_content = output.getvalue()
        
        # Generate filename
        filename = "goals_objectives_export.csv"
        if student_uic:
            filename = f"goals_{student_uic}.csv"
        elif goal_category:
            filename = f"goals_{goal_category.replace(' ', '_')}.csv"
        
        def generate_csv():
            yield csv_content
        
        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting goals: {str(e)}")
