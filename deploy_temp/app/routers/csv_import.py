from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from io import StringIO

from app.db.database import get_db
from app.services.csv_import_service import CSVImportService
from app.schemas.csv_import import CSVImportRequest, CSVImportResult, generate_csv_template, generate_caseload_template


router = APIRouter(prefix="/api/csv", tags=["csv-import"])


@router.get("/template")
def download_csv_template():
    """Download a CSV template for student import"""
    
    template_content = generate_csv_template()
    
    # Create a streaming response
    def generate_csv():
        yield template_content
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_import_template.csv"}
    )


@router.get("/caseload-template")
def download_caseload_template():
    """Download a CSV template that matches the caseload.csv format from IEP legacy system"""
    
    template_content = generate_caseload_template()
    
    # Create a streaming response
    def generate_csv():
        yield template_content
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=caseload_template.csv"}
    )


@router.post("/preview", response_model=dict)
def preview_csv_import(
    file: UploadFile = File(...),
    max_rows: int = Query(10, ge=1, le=50, description="Maximum rows to preview"),
    db: Session = Depends(get_db)
):
    """
    Preview CSV import - validate and show what would be imported
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
        import_service = CSVImportService(db)
        
        # Validate and preview
        preview_result = import_service.validate_csv_preview(csv_content, max_rows)
        
        return {
            "filename": file.filename,
            "file_size": len(content),
            **preview_result
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@router.post("/import", response_model=CSVImportResult)
def import_students_csv(
    file: UploadFile = File(...),
    skip_duplicates: bool = Query(True, description="Skip rows with duplicate UICs"),
    update_existing: bool = Query(False, description="Update existing students if UIC matches"),
    db: Session = Depends(get_db)
):
    """
    Import students from CSV file
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
        import_service = CSVImportService(db)
        
        # Import students
        result = import_service.import_students_from_csv(
            csv_content=csv_content,
            skip_duplicates=skip_duplicates,
            update_existing=update_existing
        )
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing students: {str(e)}")


@router.post("/import-text", response_model=CSVImportResult)
def import_students_csv_text(
    request: CSVImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import students from CSV text content (alternative to file upload)
    """
    
    try:
        # Create import service
        import_service = CSVImportService(db)
        
        # Import students
        result = import_service.import_students_from_csv(
            csv_content=request.file_content,
            skip_duplicates=request.skip_duplicates,
            update_existing=request.update_existing
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing students: {str(e)}")


@router.get("/export")
def export_students_csv(
    enrollment_status: Optional[str] = Query(None, description="Filter by enrollment status"),
    case_manager: Optional[str] = Query(None, description="Filter by case manager"),
    db: Session = Depends(get_db)
):
    """
    Export existing students to CSV format
    """
    
    from app.repositories.student_repository import StudentRepository
    import csv
    
    try:
        # Get students based on filters
        student_repo = StudentRepository(db)
        
        if case_manager:
            students = student_repo.get_students_by_case_manager(case_manager)
        else:
            students = student_repo.list_students(enrollment_status=enrollment_status)
        
        # Generate CSV content
        output = StringIO()
        fieldnames = [
            'first', 'last', 'uic', 'grade_level', 'teacher_name', 
            'case_manager', 'enrollment_status', 'date_of_birth'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for student in students:
            writer.writerow({
                'first': student.first,
                'last': student.last,
                'uic': student.uic or '',
                'grade_level': student.grade_level or '',
                'teacher_name': student.teacher_name or '',
                'case_manager': student.case_manager or '',
                'enrollment_status': student.enrollment_status,
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else ''
            })
        
        csv_content = output.getvalue()
        
        # Generate filename
        filename = "students_export.csv"
        if case_manager:
            filename = f"students_{case_manager.replace(' ', '_')}.csv"
        elif enrollment_status:
            filename = f"students_{enrollment_status.lower()}.csv"
        
        def generate_csv():
            yield csv_content
        
        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting students: {str(e)}")
