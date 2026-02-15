import { BaseApiService } from './base';

// Types for scheduling students
export interface TeacherAssignmentForScheduling {
  teacher_id: number;
  teacher_name: string;
  subject?: string;
  is_primary: boolean;
}

export interface SchoolForScheduling {
  id: number;
  name: string;
  district_name?: string;
}

export interface AppointmentSummaryForStudent {
  id: number;
  start_datetime: string;
  end_datetime: string;
  appointment_type: string;
  status: string;
  teacher_name?: string;
  location?: string;
}

export interface StudentScheduleView {
  // Basic student info
  id: number;
  first: string;
  last: string;
  uic?: string;
  grade_level?: string;
  case_manager_name?: string;  // Updated to match backend
  enrollment_status: string;
  
  // School relationship
  school_id?: number;
  school?: SchoolForScheduling;
  
  // Teacher relationships
  teacher_assignments: TeacherAssignmentForScheduling[];
  primary_teacher?: TeacherAssignmentForScheduling;
  
  // Scheduling summary
  current_appointments: AppointmentSummaryForStudent[];
  appointment_count: number;
  has_appointments: boolean;
  
  // Computed properties
  full_name: string;
  school_name: string;
  primary_teacher_name: string;
}

export interface StudentScheduleFilters {
  school_id?: number;
  teacher_id?: number;
  grade_level?: string;
  enrollment_status?: string;
  start_date?: string;
  end_date?: string;
  has_appointments?: boolean;
}

class SchedulingStudentsApiService extends BaseApiService {
  constructor() {
    super('/api/scheduling');
  }

  async getStudentsForScheduling(filters?: StudentScheduleFilters): Promise<StudentScheduleView[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, value.toString());
        }
      });
    }

    const data = await this.get<StudentScheduleView[]>(`/students?${params.toString()}`);
    console.log('📦 Raw scheduling students response:', data);
    return data;
  }

  async getStudentForScheduling(studentId: number): Promise<StudentScheduleView> {
    return this.get<StudentScheduleView>(`/students/${studentId}`);
  }
}

// Export singleton instance
export const schedulingStudentsApi = new SchedulingStudentsApiService();
