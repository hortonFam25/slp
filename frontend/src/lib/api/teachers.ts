import { BaseApiService } from './base';
import type {
  Teacher,
  TeacherSummary,
  CreateTeacherRequest,
  UpdateTeacherRequest,
  TeachersFilters,
  TeacherStatistics,
  StudentTeacherAssignment,
  CreateStudentTeacherAssignmentRequest,
  SupportStaffRole
} from './types/teachers';
import type {
  TeacherSchoolAssignment,
  CreateTeacherSchoolAssignmentRequest
} from './types/schools';

class TeachersApiService extends BaseApiService {
  constructor() {
    super('/api');
  }

  async getTeachers(filters?: TeachersFilters): Promise<Teacher[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.is_active !== undefined) params.append('is_active', filters.is_active.toString());
      if (filters.school_id !== undefined) params.append('school_id', filters.school_id.toString());
      if (filters.role_id !== undefined) params.append('role_id', filters.role_id.toString());
      if (filters.department) params.append('department', filters.department);
      if (filters.search) params.append('search', filters.search);
      if (filters.skip !== undefined) params.append('skip', filters.skip.toString());
      if (filters.limit !== undefined) params.append('limit', filters.limit.toString());
    }

    const query = params.toString();
    return this.get(`/teachers${query ? '?' + query : ''}`);
  }

  async getTeachersSummary(activeOnly = true, schoolId?: number): Promise<TeacherSummary[]> {
    const params = new URLSearchParams();
    params.append('active_only', activeOnly.toString());
    if (schoolId !== undefined) params.append('school_id', schoolId.toString());
    return this.get(`/teachers/summary?${params.toString()}`);
  }

  async getTeacher(teacherId: number): Promise<Teacher> {
    return this.get(`/teachers/${teacherId}`);
  }

  async createTeacher(teacher: CreateTeacherRequest): Promise<Teacher> {
    return this.post('/teachers', teacher);
  }

  async updateTeacher(teacherId: number, updates: UpdateTeacherRequest): Promise<Teacher> {
    return this.put(`/teachers/${teacherId}`, updates);
  }

  async deleteTeacher(teacherId: number): Promise<{ message: string }> {
    return this.delete(`/teachers/${teacherId}`);
  }

  async getTeachersBySchool(schoolId: number, currentOnly = true): Promise<TeacherSummary[]> {
    const params = new URLSearchParams();
    params.append('current_only', currentOnly.toString());
    return this.get(`/schools/${schoolId}/teachers?${params.toString()}`);
  }

  async getTeacherStatistics(teacherId: number): Promise<TeacherStatistics> {
    return this.get(`/teachers/${teacherId}/statistics`);
  }

  async getDepartments(): Promise<string[]> {
    return this.get('/departments');
  }

  async getRoles(activeOnly = true): Promise<SupportStaffRole[]> {
    const params = new URLSearchParams();
    params.append('active_only', activeOnly.toString());
    return this.get(`/roles?${params.toString()}`);
  }

  // Student-Teacher Assignment methods
  async assignStudentToTeacher(assignment: CreateStudentTeacherAssignmentRequest): Promise<StudentTeacherAssignment> {
    return this.post('/student-teacher-assignments', assignment);
  }

  async endStudentTeacherAssignment(assignmentId: number, endDate: string): Promise<{ message: string }> {
    const params = new URLSearchParams();
    params.append('end_date', endDate);
    return this.put(`/student-teacher-assignments/${assignmentId}/end?${params.toString()}`, {});
  }

  // Teacher-School Assignment methods
  async getTeacherSchoolAssignments(teacherId: number): Promise<TeacherSchoolAssignment[]> {
    return this.get(`/teachers/${teacherId}/school-assignments`);
  }

  async createTeacherSchoolAssignment(assignment: CreateTeacherSchoolAssignmentRequest): Promise<TeacherSchoolAssignment> {
    return this.post('/teacher-school-assignments', assignment);
  }

  async updateTeacherSchoolAssignment(assignmentId: number, updates: Partial<CreateTeacherSchoolAssignmentRequest>): Promise<TeacherSchoolAssignment> {
    return this.put(`/teacher-school-assignments/${assignmentId}`, updates);
  }

  async deleteTeacherSchoolAssignment(assignmentId: number): Promise<void> {
    return this.delete(`/teacher-school-assignments/${assignmentId}`);
  }
}

export const teachersApi = new TeachersApiService();

// Re-export types for external use
export type {
  Teacher,
  TeacherSummary,
  CreateTeacherRequest,
  UpdateTeacherRequest,
  TeachersFilters,
  TeacherStatistics,
  StudentTeacherAssignment,
  CreateStudentTeacherAssignmentRequest,
  SupportStaffRole
} from './types/teachers';