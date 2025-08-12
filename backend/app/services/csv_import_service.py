from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import date

from app.models.student import Student
from app.repositories.student_repository import StudentRepository
from app.schemas.csv_import import StudentCSVRow, CSVImportResult, parse_csv_content
from app.schemas.student import StudentCreate


class CSVImportService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.student_repo = StudentRepository(db_session)
    
    def import_students_from_csv(
        self, 
        csv_content: str, 
        skip_duplicates: bool = True,
        update_existing: bool = False
    ) -> CSVImportResult:
        """
        Import students from CSV content
        
        Args:
            csv_content: Raw CSV file content
            skip_duplicates: Skip rows where UIC already exists
            update_existing: Update existing students when UIC matches
        """
        
        # Parse CSV content
        try:
            raw_rows = parse_csv_content(csv_content)
        except ValueError as e:
            return CSVImportResult(
                total_rows=0,
                successful_imports=0,
                failed_imports=1,
                skipped_duplicates=0,
                updated_existing=0,
                errors=[{"row": 0, "error": str(e)}],
                imported_students=[]
            )
        
        result = CSVImportResult(
            total_rows=len(raw_rows),
            successful_imports=0,
            failed_imports=0,
            skipped_duplicates=0,
            updated_existing=0,
            errors=[],
            imported_students=[]
        )
        
        for raw_row in raw_rows:
            try:
                # Validate and parse the row
                row_number = raw_row.pop('_row_number', 0)
                
                # Map CSV columns to our schema (handle different column names)
                mapped_row = self._map_csv_columns(raw_row)
                
                # Validate the row data
                student_data = StudentCSVRow(**mapped_row)
                
                # Check for existing student by UIC
                existing_student = None
                if student_data.uic:
                    existing_student = self.student_repo.get_student_by_uic(student_data.uic)
                
                if existing_student:
                    if skip_duplicates and not update_existing:
                        result.skipped_duplicates += 1
                        continue
                    elif update_existing:
                        # Update existing student
                        updated_student = self._update_existing_student(existing_student, student_data)
                        result.updated_existing += 1
                        result.imported_students.append({
                            "id": updated_student.id,
                            "name": f"{updated_student.first} {updated_student.last}",
                            "uic": updated_student.uic,
                            "action": "updated"
                        })
                        continue
                
                # Create new student
                new_student = self._create_new_student(student_data)
                result.successful_imports += 1
                result.imported_students.append({
                    "id": new_student.id,
                    "name": f"{new_student.first} {new_student.last}",
                    "uic": new_student.uic,
                    "action": "created"
                })
                
            except Exception as e:
                result.failed_imports += 1
                result.errors.append({
                    "row": row_number,
                    "error": str(e),
                    "data": raw_row
                })
        
        return result
    
    def _map_csv_columns(self, raw_row: Dict[str, Any]) -> Dict[str, Any]:
        """Map various CSV column names to our standard field names"""
        
        # Column mapping for different possible CSV formats
        column_mappings = {
            # Standard mappings
            'first_name': 'first',
            'firstname': 'first',
            'last_name': 'last',
            'lastname': 'last',
            'student_id': 'uic',
            'student_number': 'uic',
            'id': 'uic',
            'grade': 'grade_level',
            'teacher': 'teacher_name',
            'classroom_teacher': 'teacher_name',
            'slp': 'case_manager',
            'speech_therapist': 'case_manager',
            'therapist': 'case_manager',
            'status': 'enrollment_status',
            'dob': 'date_of_birth',
            'birth_date': 'date_of_birth',
            'birthdate': 'date_of_birth',
        }
        
        mapped_row = {}
        
        # First, add direct matches
        for field in ['first', 'last', 'uic', 'grade_level', 'teacher_name', 'case_manager', 'enrollment_status', 'date_of_birth']:
            if field in raw_row:
                mapped_row[field] = raw_row[field]
        
        # Then, apply column mappings
        for csv_col, our_field in column_mappings.items():
            if csv_col in raw_row and our_field not in mapped_row:
                mapped_row[our_field] = raw_row[csv_col]
        
        return mapped_row
    
    def _create_new_student(self, student_data: StudentCSVRow) -> Student:
        """Create a new student from CSV data"""
        
        # Convert to StudentCreate schema
        create_data = StudentCreate(
            first=student_data.first,
            last=student_data.last,
            uic=student_data.uic,
            grade_level=student_data.grade_level,
            teacher_name=student_data.teacher_name,
            case_manager=student_data.case_manager,
            enrollment_status=student_data.enrollment_status,
            date_of_birth=date.fromisoformat(student_data.date_of_birth) if student_data.date_of_birth else None
        )
        
        return self.student_repo.create_student(create_data)
    
    def _update_existing_student(self, existing_student: Student, student_data: StudentCSVRow) -> Student:
        """Update an existing student with CSV data"""
        
        from app.schemas.student import StudentUpdate
        
        # Create update data - only update fields that have values in CSV
        update_fields = {}
        
        if student_data.first:
            update_fields['first'] = student_data.first
        if student_data.last:
            update_fields['last'] = student_data.last
        if student_data.grade_level:
            update_fields['grade_level'] = student_data.grade_level
        if student_data.teacher_name:
            update_fields['teacher_name'] = student_data.teacher_name
        if student_data.case_manager:
            update_fields['case_manager'] = student_data.case_manager
        if student_data.enrollment_status:
            update_fields['enrollment_status'] = student_data.enrollment_status
        if student_data.date_of_birth:
            update_fields['date_of_birth'] = date.fromisoformat(student_data.date_of_birth)
        
        update_data = StudentUpdate(**update_fields)
        return self.student_repo.update_student(existing_student.id, update_data)
    
    def validate_csv_preview(self, csv_content: str, max_preview_rows: int = 10) -> Dict[str, Any]:
        """
        Validate CSV and return preview of what would be imported
        """
        try:
            raw_rows = parse_csv_content(csv_content)
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
                mapped_row = self._map_csv_columns(raw_row)
                student_data = StudentCSVRow(**mapped_row)
                
                # Check for existing UIC
                existing_student = None
                if student_data.uic:
                    existing_student = self.student_repo.get_student_by_uic(student_data.uic)
                
                preview_rows.append({
                    "row_number": row_number,
                    "data": student_data.dict(),
                    "status": "update" if existing_student else "create",
                    "existing_student": {
                        "id": existing_student.id,
                        "name": f"{existing_student.first} {existing_student.last}"
                    } if existing_student else None,
                    "valid": True
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
