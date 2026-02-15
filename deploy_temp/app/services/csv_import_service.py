from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import date

from app.models.student import Student
from app.models.school import School
from app.repositories.student_repository import StudentRepository
from app.repositories.school_repository import SchoolRepository
from app.schemas.csv_import import StudentCSVRow, CSVImportResult, parse_csv_content
from app.schemas.student import StudentCreate


class CSVImportService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.student_repo = StudentRepository(db_session)
        self.school_repo = SchoolRepository(db_session)
    
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
                
                # Extract school name before validation (not part of StudentCSVRow)
                school_name = mapped_row.pop('school_name', None)
                
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
                new_student = self._create_new_student(student_data, school_name)
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
            
            # Caseload.csv specific mappings (IEP legacy system format)
            'first_name': 'first',
            'last_name': 'last',
            'case_manager': 'case_manager',
            'ann_rev_due_date': 'annual_review_due_date',
            're_eval_due_date': 'reevaluation_due_date',
            're_eval_most_recent': 'iep_date',
            'school': 'school_name',
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
        
        # Handle special processing for caseload.csv format
        mapped_row = self._process_caseload_format(raw_row, mapped_row)
        
        return mapped_row
    
    def _process_caseload_format(self, raw_row: Dict[str, Any], mapped_row: Dict[str, Any]) -> Dict[str, Any]:
        """Special processing for caseload.csv format from IEP legacy system"""
        
        # Handle first and last name mapping from caseload format
        if 'first_name' in raw_row and raw_row['first_name']:
            mapped_row['first'] = raw_row['first_name'].strip()
        if 'last_name' in raw_row and raw_row['last_name']:
            mapped_row['last'] = raw_row['last_name'].strip()
        if 'id' in raw_row and raw_row['id']:
            mapped_row['uic'] = raw_row['id'].strip()
        
        # Normalize grade level from complex formats to simple ones
        if 'grade' in raw_row and raw_row['grade']:
            grade = raw_row['grade'].strip()
            if grade:
                # Map complex grade formats to simple ones
                if 'kindergarten' in grade.lower():
                    mapped_row['grade_level'] = 'K'
                elif 'early childhood' in grade.lower() or 'early on' in grade.lower():
                    mapped_row['grade_level'] = 'PreK'
                elif grade.isdigit():
                    mapped_row['grade_level'] = grade
                else:
                    # Try to extract number from grade string
                    import re
                    grade_match = re.search(r'\b(\d+)\b', grade)
                    if grade_match:
                        mapped_row['grade_level'] = grade_match.group(1)
                    else:
                        mapped_row['grade_level'] = grade  # Keep original if can't parse
        
        # Process case manager name from "Last,First" format to "First Last"
        if 'case_manager' in raw_row and raw_row['case_manager']:
            case_manager = raw_row['case_manager'].strip()
            if ',' in case_manager:
                # Split "Last,First" and reformat to "First Last"
                parts = case_manager.split(',', 1)
                if len(parts) == 2:
                    last_name = parts[0].strip()
                    first_name = parts[1].strip()
                    mapped_row['case_manager'] = f"{first_name} {last_name}"
            else:
                mapped_row['case_manager'] = case_manager
        
        # Convert date formats from M/d/yyyy to yyyy-MM-dd
        date_fields = [
            ('re_eval_most_recent', 'iep_date'),
            ('ann_rev_due_date', 'annual_review_due_date'), 
            ('re_eval_due_date', 'reevaluation_due_date')
        ]
        
        for csv_field, our_field in date_fields:
            if csv_field in raw_row and raw_row[csv_field]:
                date_str = raw_row[csv_field].strip()
                if date_str:
                    try:
                        # Parse M/d/yyyy format and convert to yyyy-MM-dd
                        from datetime import datetime
                        parsed_date = datetime.strptime(date_str, '%m/%d/%Y')
                        mapped_row[our_field] = parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        # If parsing fails, keep original value
                        mapped_row[our_field] = date_str
        
        # Store school name (not part of StudentCSVRow but we can track it)
        if 'school' in raw_row and raw_row['school']:
            mapped_row['school_name'] = raw_row['school'].strip()
        
        # Set default enrollment status for caseload imports
        if 'enrollment_status' not in mapped_row:
            mapped_row['enrollment_status'] = 'Active'
        
        return mapped_row
    
    def _find_or_create_school(self, school_name: str) -> Optional[int]:
        """Find existing school or create new one by name"""
        if not school_name or not school_name.strip():
            return None
            
        school_name = school_name.strip()
        
        # Clean up school name - remove "(CLOSED)" suffix if present
        clean_name = school_name.replace(" (CLOSED)", "").strip()
        
        # Try to find existing school by exact name match
        existing_school = None
        try:
            schools = self.school_repo.list_schools()
            for school in schools:
                if school.name.lower() == clean_name.lower():
                    existing_school = school
                    break
        except Exception:
            # If school repository doesn't have list_schools, try a different approach
            from sqlalchemy import func
            existing_school = self.db.query(School).filter(
                func.lower(School.name) == clean_name.lower()
            ).first()
        
        if existing_school:
            return existing_school.id
        
        # Create new school if not found
        try:
            from app.schemas.school import SchoolCreate
            new_school_data = SchoolCreate(
                name=clean_name,
                is_active=not "(CLOSED)" in school_name  # Mark as inactive if name contains "CLOSED"
            )
            new_school = self.school_repo.create_school(new_school_data)
            return new_school.id
        except Exception as e:
            # If we can't create the school, just return None and log the issue
            print(f"Warning: Could not create school '{clean_name}': {e}")
            return None
    
    def _create_new_student(self, student_data: StudentCSVRow, school_name: str = None) -> Student:
        """Create a new student from CSV data"""
        
        # Find or create school if school name is provided
        school_id = None
        if school_name:
            school_id = self._find_or_create_school(school_name)
        
        # Convert to StudentCreate schema
        create_data = StudentCreate(
            first=student_data.first,
            last=student_data.last,
            uic=student_data.uic,
            grade_level=student_data.grade_level,
            teacher_name=student_data.teacher_name,
            case_manager=student_data.case_manager,
            enrollment_status=student_data.enrollment_status,
            school_id=school_id,
            date_of_birth=date.fromisoformat(student_data.date_of_birth) if student_data.date_of_birth else None,
            # Include IEP date fields
            iep_date=date.fromisoformat(student_data.iep_date) if student_data.iep_date else None,
            annual_review_due_date=date.fromisoformat(student_data.annual_review_due_date) if student_data.annual_review_due_date else None,
            reevaluation_due_date=date.fromisoformat(student_data.reevaluation_due_date) if student_data.reevaluation_due_date else None,
            iep_meeting_date=date.fromisoformat(student_data.iep_meeting_date) if student_data.iep_meeting_date else None,
            initial_evaluation_date=date.fromisoformat(student_data.initial_evaluation_date) if student_data.initial_evaluation_date else None,
            eligibility_determination_date=date.fromisoformat(student_data.eligibility_determination_date) if student_data.eligibility_determination_date else None
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
        
        # Include IEP date fields in updates
        if student_data.iep_date:
            update_fields['iep_date'] = date.fromisoformat(student_data.iep_date)
        if student_data.annual_review_due_date:
            update_fields['annual_review_due_date'] = date.fromisoformat(student_data.annual_review_due_date)
        if student_data.reevaluation_due_date:
            update_fields['reevaluation_due_date'] = date.fromisoformat(student_data.reevaluation_due_date)
        if student_data.iep_meeting_date:
            update_fields['iep_meeting_date'] = date.fromisoformat(student_data.iep_meeting_date)
        if student_data.initial_evaluation_date:
            update_fields['initial_evaluation_date'] = date.fromisoformat(student_data.initial_evaluation_date)
        if student_data.eligibility_determination_date:
            update_fields['eligibility_determination_date'] = date.fromisoformat(student_data.eligibility_determination_date)
        
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
                
                # Extract school name before validation (not part of StudentCSVRow)
                school_name = mapped_row.pop('school_name', None)
                
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
