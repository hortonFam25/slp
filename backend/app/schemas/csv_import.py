from pydantic import BaseModel, Field, validator
from typing import List, Optional, Any
from datetime import date
import csv
from io import StringIO


class StudentCSVRow(BaseModel):
    """Schema for a single row in the student CSV import"""
    first: str = Field(..., min_length=1, max_length=100, description="First name")
    last: str = Field(..., min_length=1, max_length=100, description="Last name")
    uic: Optional[str] = Field(None, max_length=50, description="Unique Identifier Code from legacy IEP system")
    grade_level: Optional[str] = Field(None, max_length=10, description="Grade level (K, 1, 2, etc.)")
    teacher_name: Optional[str] = Field(None, max_length=100, description="Classroom teacher name")
    case_manager: Optional[str] = Field(None, max_length=100, description="Case manager/SLP name")
    enrollment_status: str = Field("Active", max_length=20, description="Enrollment status")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    
    # IEP Date Fields
    iep_date: Optional[str] = Field(None, description="Current IEP date (YYYY-MM-DD)")
    annual_review_due_date: Optional[str] = Field(None, description="Annual review due date (YYYY-MM-DD)")
    reevaluation_due_date: Optional[str] = Field(None, description="Re-evaluation due date (YYYY-MM-DD)")
    iep_meeting_date: Optional[str] = Field(None, description="Last IEP meeting date (YYYY-MM-DD)")
    initial_evaluation_date: Optional[str] = Field(None, description="Initial evaluation date (YYYY-MM-DD)")
    eligibility_determination_date: Optional[str] = Field(None, description="Eligibility determination date (YYYY-MM-DD)")
    
    @validator('enrollment_status')
    def validate_enrollment_status(cls, v):
        valid_statuses = ['Active', 'Inactive', 'Transferred']
        if v not in valid_statuses:
            raise ValueError(f'Enrollment status must be one of: {", ".join(valid_statuses)}')
        return v
    
    @validator('date_of_birth', 'iep_date', 'annual_review_due_date', 'reevaluation_due_date', 
               'iep_meeting_date', 'initial_evaluation_date', 'eligibility_determination_date')
    def validate_date_fields(cls, v):
        if v and v.strip():
            try:
                # Try to parse the date to validate format
                date.fromisoformat(v.strip())
                return v.strip()
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return None
    
    @validator('first', 'last')
    def validate_names(cls, v):
        if not v or not v.strip():
            raise ValueError('First and last names are required')
        return v.strip()
    
    @validator('uic', 'grade_level', 'teacher_name', 'case_manager', 
               'iep_date', 'annual_review_due_date', 'reevaluation_due_date',
               'iep_meeting_date', 'initial_evaluation_date', 'eligibility_determination_date', pre=True)
    def strip_optional_fields(cls, v):
        return v.strip() if v and isinstance(v, str) else v


class CSVImportRequest(BaseModel):
    """Request model for CSV import"""
    file_content: str = Field(..., description="CSV file content as string")
    skip_duplicates: bool = Field(True, description="Skip rows with duplicate UICs")
    update_existing: bool = Field(False, description="Update existing students if UIC matches")


class CSVImportResult(BaseModel):
    """Result of CSV import operation"""
    total_rows: int
    successful_imports: int
    failed_imports: int
    skipped_duplicates: int
    updated_existing: int
    errors: List[dict]
    imported_students: List[dict]


class CSVTemplateResponse(BaseModel):
    """Response for CSV template download"""
    filename: str
    content: str
    headers: List[str]


def parse_csv_content(csv_content: str) -> List[dict]:
    """Parse CSV content and return list of dictionaries"""
    try:
        # Handle different line endings
        csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Parse CSV
        reader = csv.DictReader(StringIO(csv_content))
        rows = []
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 since header is row 1
            # Clean up the row data
            cleaned_row = {}
            for key, value in row.items():
                if key:  # Skip empty column headers
                    cleaned_key = key.strip().lower().replace(' ', '_')
                    cleaned_row[cleaned_key] = value.strip() if value else None
            
            if cleaned_row:  # Skip empty rows
                cleaned_row['_row_number'] = row_num
                rows.append(cleaned_row)
        
        return rows
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


def generate_csv_template() -> str:
    """Generate a CSV template with sample data"""
    headers = [
        'first',
        'last', 
        'uic',
        'grade_level',
        'teacher_name',
        'case_manager',
        'enrollment_status',
        'date_of_birth',
        'iep_date',
        'annual_review_due_date',
        'reevaluation_due_date',
        'iep_meeting_date',
        'initial_evaluation_date',
        'eligibility_determination_date'
    ]
    
    sample_data = [
        {
            'first': 'John',
            'last': 'Doe',
            'uic': 'IEP001',
            'grade_level': '3',
            'teacher_name': 'Ms. Johnson',
            'case_manager': 'Sarah Thompson',
            'enrollment_status': 'Active',
            'date_of_birth': '2015-08-15',
            'iep_date': '2023-07-17',
            'annual_review_due_date': '2024-07-16',
            'reevaluation_due_date': '2026-07-16',
            'iep_meeting_date': '2023-07-17',
            'initial_evaluation_date': '2020-03-15',
            'eligibility_determination_date': '2020-04-01'
        },
        {
            'first': 'Jane',
            'last': 'Smith',
            'uic': 'IEP002',
            'grade_level': 'K',
            'teacher_name': 'Mr. Davis',
            'case_manager': 'Sarah Thompson',
            'enrollment_status': 'Active',
            'date_of_birth': '2018-03-22',
            'iep_date': '2022-09-23',
            'annual_review_due_date': '2023-09-22',
            'reevaluation_due_date': '2025-09-22',
            'iep_meeting_date': '2022-09-23',
            'initial_evaluation_date': '2021-08-10',
            'eligibility_determination_date': '2021-09-15'
        }
    ]
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(sample_data)
    
    return output.getvalue()
