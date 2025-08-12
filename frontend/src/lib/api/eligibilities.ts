import { BaseApiService } from './base';
import { API_ENDPOINTS } from './types';
import { EligibilityCategory, StudentEligibility } from './students';

// Request/Response interfaces for eligibility management
export interface CreateStudentEligibilityRequest {
  student_id: number;
  eligibility_category_id: number;
  start_date: string;
  end_date?: string;
  is_primary: boolean;
  notes?: string;
}

export interface UpdateStudentEligibilityRequest {
  eligibility_category_id?: number;
  start_date?: string;
  end_date?: string;
  is_primary?: boolean;
  notes?: string;
}

class EligibilitiesApiService extends BaseApiService {
  constructor() {
    super(API_ENDPOINTS.ELIGIBILITIES);
  }

  // Get all available eligibility categories
  async getEligibilityCategories(activeOnly: boolean = true): Promise<EligibilityCategory[]> {
    const params = activeOnly ? '?active_only=true' : '?active_only=false';
    return this.get<EligibilityCategory[]>(`/categories${params}`);
  }

  // Get all eligibilities for a specific student
  async getStudentEligibilities(studentId: number): Promise<StudentEligibility[]> {
    return this.get<StudentEligibility[]>(`/students/${studentId}`);
  }

  // Create a new student eligibility
  async createStudentEligibility(data: CreateStudentEligibilityRequest): Promise<StudentEligibility> {
    return this.post<StudentEligibility>('/students', data);
  }

  // Update an existing student eligibility
  async updateStudentEligibility(eligibilityId: number, data: UpdateStudentEligibilityRequest): Promise<StudentEligibility> {
    return this.put<StudentEligibility>(`/students/${eligibilityId}`, data);
  }

  // Delete a student eligibility
  async deleteStudentEligibility(eligibilityId: number): Promise<void> {
    return this.delete<void>(`/students/${eligibilityId}`);
  }
}

export const eligibilitiesApi = new EligibilitiesApiService();
