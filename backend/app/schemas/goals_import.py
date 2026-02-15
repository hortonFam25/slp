from pydantic import BaseModel, Field, validator
from typing import List, Optional, Any
from datetime import date
import csv
from io import StringIO


class ObjectiveImportData(BaseModel):
    """Schema for importing a single objective with progress"""
    objective_description: str = Field(..., min_length=1, description="Objective description")
    schedule_frequency: Optional[str] = Field(None, description="Schedule frequency (e.g., Monthly, Weekly)")
    progress_comments: Optional[str] = Field(None, description="Progress comments")
    progress_date: Optional[str] = Field(None, description="Progress date (YYYY-MM-DD)")
    
    @validator('progress_date')
    def validate_progress_date(cls, v):
        if v and str(v).strip():
            try:
                # Try to parse the date to validate format
                date.fromisoformat(str(v).strip())
                return str(v).strip()
            except ValueError:
                raise ValueError('Progress date must be in YYYY-MM-DD format')
        return None


class GoalImportRow(BaseModel):
    """Schema for a single row in the goals CSV import"""
    student_uic: str = Field(..., min_length=1, description="Student UIC from legacy system")
    goal_description: str = Field(..., min_length=1, description="IEP Goal description")
    responsible_staff: Optional[str] = Field(None, description="Responsible staff member")
    goal_category: Optional[str] = Field("Speech/Language", description="Goal category")
    start_date: Optional[str] = Field(None, description="Goal start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Goal end date (YYYY-MM-DD)")
    target_criteria: Optional[str] = Field("80% accuracy over 3 consecutive sessions", description="Target criteria")
    
    # Up to 5 objectives with progress data
    objectives: List[ObjectiveImportData] = Field(default_factory=list, max_items=5)
    
    @validator('student_uic', 'goal_description')
    def validate_required_fields(cls, v):
        if not v or not str(v).strip():
            raise ValueError('Student UIC and Goal description are required')
        return str(v).strip()
    
    @validator('start_date', 'end_date')
    def validate_date_fields(cls, v):
        if v and str(v).strip():
            try:
                date.fromisoformat(str(v).strip())
                return str(v).strip()
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return None


class GoalsImportRequest(BaseModel):
    """Request model for goals CSV import"""
    file_content: str = Field(..., description="CSV file content as string")
    skip_duplicates: bool = Field(True, description="Skip goals for students that already have goals")
    update_existing: bool = Field(False, description="Update existing goals if student already has goals")
    default_goal_category: str = Field("Speech/Language", description="Default goal category")


class GoalsImportResult(BaseModel):
    """Result of goals CSV import operation"""
    total_rows: int
    successful_imports: int
    failed_imports: int
    skipped_duplicates: int
    updated_existing: int
    goals_created: int
    objectives_created: int
    progress_entries_created: int
    errors: List[dict]
    imported_goals: List[dict]


def parse_goals_csv_content(csv_content: str) -> List[dict]:
    """Parse goals CSV content and return list of dictionaries"""
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
                    cleaned_key = key.strip()
                    # Handle None values properly
                    if value is None:
                        cleaned_row[cleaned_key] = None
                    else:
                        cleaned_value = str(value).strip()
                        cleaned_row[cleaned_key] = cleaned_value if cleaned_value else None
            
            if cleaned_row and cleaned_row.get('ID'):  # Skip empty rows and rows without ID
                cleaned_row['_row_number'] = row_num
                rows.append(cleaned_row)
        
        return rows
    except Exception as e:
        raise ValueError(f"Error parsing CSV: {str(e)}")


def convert_legacy_csv_to_goal_import(raw_row: dict) -> GoalImportRow:
    """Convert legacy CSV format to GoalImportRow format"""
    
    # Extract basic goal information with better null handling
    id_value = raw_row.get('ID')
    goal_value = raw_row.get('Goal') 
    staff_value = raw_row.get('Responsible Staff')
    
    student_uic = str(id_value).strip() if id_value is not None else ''
    goal_description = str(goal_value).strip() if goal_value is not None else ''
    responsible_staff = str(staff_value).strip() if staff_value is not None else ''
    
    # Process objectives (up to 5, but legacy format has up to 3)
    objectives = []
    
    for i in range(1, 6):  # Support up to 5 objectives
        # Try multiple possible column name formats for flexibility
        obj_key = None
        schedule_key = None
        progress_key = None
        date_key = None
        
        # Find objective column
        for possible_obj_key in [f'Objective{i}', f'objective{i}']:
            if possible_obj_key in raw_row:
                obj_key = possible_obj_key
                break
        
        # Find schedule column
        for possible_schedule_key in [f'Schedule{i}', f'schedule{i}']:
            if possible_schedule_key in raw_row:
                schedule_key = possible_schedule_key
                break
        
        # Find progress comments column
        for possible_progress_key in [f'Prog Comments {i}', f'progcomments{i}', f'prog comments {i}']:
            if possible_progress_key in raw_row:
                progress_key = possible_progress_key
                break
        
        # Find date column - be extra flexible here due to CSV inconsistencies
        for possible_date_key in [f'prog Date{i}', f'prog Date{i} ', f'progdate{i}', f'prog date{i}', f'progDate{i}']:
            if possible_date_key in raw_row:
                date_key = possible_date_key
                break
        
        if not obj_key:
            continue  # Skip if we can't find the objective column
        
        # Get objective description with better null handling
        obj_value = raw_row.get(obj_key)
        objective_desc = str(obj_value).strip() if obj_value is not None else ''
        
        if objective_desc:  # Only add if objective description exists
            # Handle schedule frequency
            schedule_freq = None
            if schedule_key:
                schedule_value = raw_row.get(schedule_key)
                schedule_freq = str(schedule_value).strip() if schedule_value is not None else None
                schedule_freq = schedule_freq if schedule_freq else None
            
            # Handle progress comments
            progress_comments = None
            if progress_key:
                progress_value = raw_row.get(progress_key)
                progress_comments = str(progress_value).strip() if progress_value is not None else None
                progress_comments = progress_comments if progress_comments else None
            
            # Handle progress date
            progress_date_str = ''
            if date_key:
                date_value = raw_row.get(date_key)
                progress_date_str = str(date_value).strip() if date_value is not None else ''
            
            # Parse progress date
            progress_date = None
            if progress_date_str:
                try:
                    # Handle different date formats (M/D/YYYY, MM/DD/YYYY, etc.)
                    from datetime import datetime
                    parsed_date = datetime.strptime(progress_date_str, '%m/%d/%Y')
                    progress_date = parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    try:
                        # Try other common formats
                        parsed_date = datetime.strptime(progress_date_str, '%m/%d/%y')
                        progress_date = parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        # If all else fails, keep original and let validation handle it
                        progress_date = progress_date_str
            
            objectives.append(ObjectiveImportData(
                objective_description=objective_desc,
                schedule_frequency=schedule_freq,
                progress_comments=progress_comments,
                progress_date=progress_date
            ))
    
    # Validate required fields before creating GoalImportRow
    if not student_uic:
        raise ValueError("Student ID is required but was empty")
    if not goal_description:
        raise ValueError("Goal description is required but was empty")
    
    return GoalImportRow(
        student_uic=student_uic,
        goal_description=goal_description,
        responsible_staff=responsible_staff,
        objectives=objectives
    )


def generate_goals_csv_template() -> str:
    """Generate a CSV template for goals and objectives import"""
    headers = [
        'ID',
        'Goal',
        'Responsible Staff',
        'Objective1',
        'Schedule1',
        'Prog Comments 1',
        'prog Date1 ',  # Note: extra space to match your CSV format
        'Objective2',
        'Schedule2',
        'progdate2',  # Note: different format to match your CSV
        'Objective3',
        'Schedule3',
        'prog Date3',
        'Objective4',
        'Schedule4',
        'prog Date4',
        'Objective5',
        'Schedule5',
        'prog Date5'
    ]
    
    sample_data = [
        {
            'ID': '1234567890',
            'Goal': 'Student will improve expressive language skills by using 4-5 word utterances with a variety of sentence structures during structured and natural settings.',
            'Responsible Staff': 'Speech Pathologist',
            'Objective1': 'Student will combine 3-4 words to describe actions and locations in structured activities',
            'Schedule1': 'Monthly updates',
            'Prog Comments 1': 'Student is producing 3-4 word phrases in 4 out of 5 opportunities on average.',
            'prog Date1': '2/24/2025',
            'Objective2': 'Student will form 4-5 word sentences using different sentence structures in structured activities',
            'Schedule2': 'Monthly updates',
            'Prog Comments 2': 'Working on expanding sentence length with visual supports.',
            'prog Date2': '2/24/2025',
            'Objective3': 'Student will spontaneously produce 4-5 word sentences in response to questions',
            'Schedule3': 'Monthly updates',
            'Prog Comments 3': 'Beginning to show spontaneous use of longer phrases.',
            'prog Date3': '2/24/2025',
            'Objective4': '',
            'Schedule4': '',
            'Prog Comments 4': '',
            'prog Date4': '',
            'Objective5': '',
            'Schedule5': '',
            'Prog Comments 5': '',
            'prog Date5': ''
        }
    ]
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(sample_data)
    
    return output.getvalue()
