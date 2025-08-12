import { BaseApiService } from './base';
import type {
  School,
  SchoolSummary,
  CreateSchoolRequest,
  UpdateSchoolRequest,
  SchoolsFilters,
  SchoolStatistics,
  TeacherSchoolAssignment,
  CreateTeacherSchoolAssignmentRequest
} from './types/schools';

class SchoolsApiService extends BaseApiService {
  constructor() {
    super('/api');
  }

  async getSchools(filters?: SchoolsFilters): Promise<School[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.is_active !== undefined) params.append('is_active', filters.is_active.toString());
      if (filters.district) params.append('district', filters.district);
      if (filters.search) params.append('search', filters.search);
      if (filters.skip !== undefined) params.append('skip', filters.skip.toString());
      if (filters.limit !== undefined) params.append('limit', filters.limit.toString());
    }

    const query = params.toString();
    return this.get(`/schools${query ? '?' + query : ''}`);
  }

  async getSchoolsSummary(activeOnly = true): Promise<SchoolSummary[]> {
    const params = new URLSearchParams();
    params.append('active_only', activeOnly.toString());
    return this.get(`/schools/summary?${params.toString()}`);
  }

  async getSchool(schoolId: number): Promise<School> {
    return this.get(`/schools/${schoolId}`);
  }

  async createSchool(school: CreateSchoolRequest): Promise<School> {
    return this.post('/schools', school);
  }

  async updateSchool(schoolId: number, updates: UpdateSchoolRequest): Promise<School> {
    return this.put(`/schools/${schoolId}`, updates);
  }

  async deleteSchool(schoolId: number): Promise<{ message: string }> {
    return this.delete(`/schools/${schoolId}`);
  }

  async getSchoolsByDistrict(district: string): Promise<SchoolSummary[]> {
    return this.get(`/schools/district/${encodeURIComponent(district)}`);
  }

  async getSchoolStatistics(schoolId: number): Promise<SchoolStatistics> {
    return this.get(`/schools/${schoolId}/statistics`);
  }

  async getDistricts(): Promise<string[]> {
    return this.get('/districts');
  }

  // Teacher-School Assignment methods
  async assignTeacherToSchool(assignment: CreateTeacherSchoolAssignmentRequest): Promise<TeacherSchoolAssignment> {
    return this.post('/teacher-school-assignments', assignment);
  }

  async endTeacherSchoolAssignment(assignmentId: number, endDate: string): Promise<{ message: string }> {
    const params = new URLSearchParams();
    params.append('end_date', endDate);
    return this.put(`/teacher-school-assignments/${assignmentId}/end?${params.toString()}`, {});
  }
}

export const schoolsApi = new SchoolsApiService();
