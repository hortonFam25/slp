import { BaseApiService } from './base';
import { API_ENDPOINTS } from './types';

// Eligibility interfaces
export interface EligibilityCategory {
  id: number;
  name: string;
  code?: string;
  description?: string;
  is_active: boolean;
  display_order?: number;
  created_date: string;
  modified_date: string;
}

export interface StudentEligibility {
  id: number;
  student_id: number;
  eligibility_category_id: number;
  start_date: string;
  end_date?: string;
  is_primary: boolean;
  notes?: string;
  created_date: string;
  modified_date: string;
  eligibility_category: EligibilityCategory;
  is_active: boolean;
}

// Student data interfaces
export interface Student {
  id: number;
  first: string;
  last: string;
  uic?: string;
  grade_level?: string;
  teacher_name?: string;
  case_manager?: string;
  enrollment_status: string;
  is_archived: boolean;
  date_of_birth?: string;
  created_date: string;
  modified_date: string;
  // IEP and Evaluation dates
  iep_date?: string;
  annual_review_due_date?: string;
  reevaluation_due_date?: string;
  iep_meeting_date?: string;
  initial_evaluation_date?: string;
  eligibility_determination_date?: string;
  school_id?: number;
  // Eligibility information
  eligibilities: StudentEligibility[];
}

export interface StudentSummary {
  id: number;
  first: string;
  last: string;
  grade_level?: string;
  case_manager?: string;
  enrollment_status: string;
  is_archived: boolean;
  school_id?: number;  // Added for scheduling functionality
  uic?: string;  // Added for student identification
}

export interface CreateStudentRequest {
  first: string;
  last: string;
  uic?: string;
  grade_level?: string;
  teacher_name?: string;
  case_manager?: string;
  enrollment_status?: string;
  is_archived?: boolean;
  date_of_birth?: string;
  // IEP and Evaluation dates
  iep_date?: string;
  annual_review_due_date?: string;
  reevaluation_due_date?: string;
  iep_meeting_date?: string;
  initial_evaluation_date?: string;
  eligibility_determination_date?: string;
  school_id?: number;
}

export interface UpdateStudentRequest {
  first?: string;
  last?: string;
  uic?: string;
  grade_level?: string;
  teacher_name?: string;
  case_manager?: string;
  enrollment_status?: string;
  is_archived?: boolean;
  date_of_birth?: string;
  // IEP and Evaluation dates
  iep_date?: string;
  annual_review_due_date?: string;
  reevaluation_due_date?: string;
  iep_meeting_date?: string;
  initial_evaluation_date?: string;
  eligibility_determination_date?: string;
  school_id?: number;
}

export interface StudentsFilters {
  enrollment_status?: string;
  case_manager?: string;
  include_archived?: boolean;
}

class StudentsApiService extends BaseApiService {
  constructor() {
    super(API_ENDPOINTS.STUDENTS);
  }

  // List students with optional filtering
  async getStudents(filters?: StudentsFilters): Promise<StudentSummary[]> {
    const params: Record<string, any> = {};
    
    if (filters?.enrollment_status) {
      params.enrollment_status = filters.enrollment_status;
    }
    if (filters?.case_manager) {
      params.case_manager = filters.case_manager;
    }
    if (filters?.include_archived !== undefined) {
      params.include_archived = filters.include_archived;
    }
    
    return this.get<StudentSummary[]>('', params);
  }

  // Get a specific student by ID
  async getStudent(id: number): Promise<Student> {
    return this.get<Student>(`/${id}`);
  }

  // Get a student by UIC (for legacy integration)
  async getStudentByUic(uic: string): Promise<Student> {
    return this.get<Student>(`/uic/${uic}`);
  }

  // Create a new student
  async createStudent(data: CreateStudentRequest): Promise<Student> {
    return this.post<Student>('', data);
  }

  // Update an existing student
  async updateStudent(id: number, data: UpdateStudentRequest): Promise<Student> {
    return this.put<Student>(`/${id}`, data);
  }

  // Delete a student
  async deleteStudent(id: number): Promise<void> {
    return this.delete<void>(`/${id}`);
  }

  // Archive a student (hide from active lists but preserve data)
  async archiveStudent(id: number): Promise<Student> {
    return this.put<Student>(`/${id}/archive`, {});
  }

  // Unarchive a student (restore to active lists)
  async unarchiveStudent(id: number): Promise<Student> {
    return this.put<Student>(`/${id}/unarchive`, {});
  }

  // Get archived students
  async getArchivedStudents(): Promise<StudentSummary[]> {
    return this.get<StudentSummary[]>('/archived');
  }

  // Bulk operations (future enhancement)
  async bulkCreateStudents(students: CreateStudentRequest[]): Promise<Student[]> {
    return this.post<Student[]>('/bulk', { students });
  }

  // Get students by case manager (convenience method)
  async getStudentsByCaseManager(caseManager: string): Promise<StudentSummary[]> {
    return this.getStudents({ case_manager: caseManager });
  }

  // Get active students only (convenience method)
  async getActiveStudents(): Promise<StudentSummary[]> {
    return this.getStudents({ enrollment_status: 'Active' });
  }
}

// Export singleton instance
export const studentsApi = new StudentsApiService();

// Export for backward compatibility
export default studentsApi;
