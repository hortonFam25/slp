// School types
export interface School {
  id: number;
  name: string;
  address?: string;
  phone?: string;
  email?: string;
  district?: string;
  principal_name?: string;
  contact_person?: string;
  contact_phone?: string;
  notes?: string;
  is_active: boolean;
  created_date: string;
  modified_date: string;
  active_students_count?: number;
  active_teachers_count?: number;
}

export interface SchoolSummary {
  id: number;
  name: string;
  district?: string;
  is_active: boolean;
  active_students_count?: number;
  active_teachers_count?: number;
}

export interface CreateSchoolRequest {
  name: string;
  address?: string;
  phone?: string;
  email?: string;
  district?: string;
  principal_name?: string;
  contact_person?: string;
  contact_phone?: string;
  notes?: string;
  is_active?: boolean;
}

export interface UpdateSchoolRequest {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  district?: string;
  principal_name?: string;
  contact_person?: string;
  contact_phone?: string;
  notes?: string;
  is_active?: boolean;
}

export interface SchoolsFilters {
  is_active?: boolean;
  district?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface SchoolStatistics {
  school_id: number;
  school_name: string;
  active_students: number;
  active_teachers: number;
  grade_distribution: Array<{
    grade: string;
    count: number;
  }>;
}

// Teacher assignment types
export interface TeacherSchoolAssignment {
  id: number;
  teacher_id: number;
  school_id: number;
  start_date: string;
  end_date?: string;
  is_primary: boolean;
  notes?: string;
  created_date: string;
  modified_date: string;
  is_current: boolean;
  duration_description: string;
}

export interface CreateTeacherSchoolAssignmentRequest {
  teacher_id: number;
  school_id: number;
  start_date: string;
  end_date?: string;
  is_primary?: boolean;
  notes?: string;
}
