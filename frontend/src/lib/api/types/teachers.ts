// Teacher types
export interface Teacher {
  id: number;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  title?: string;
  department?: string;
  room_number?: string;
  preferred_contact_method?: string;
  notes?: string;
  is_active: boolean;
  created_date: string;
  modified_date: string;
  full_name: string;
  display_name: string;
  current_students_count?: number;
  primary_school_name?: string;
  current_schools_names?: string[];
  active_schools_count?: number;
}

export interface TeacherSummary {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  title?: string;
  display_name: string;
  email?: string;
  is_active: boolean;
  current_students_count?: number;
}

export interface CreateTeacherRequest {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  title?: string;
  department?: string;
  room_number?: string;
  preferred_contact_method?: string;
  notes?: string;
  is_active?: boolean;
}

export interface UpdateTeacherRequest {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  title?: string;
  department?: string;
  room_number?: string;
  preferred_contact_method?: string;
  notes?: string;
  is_active?: boolean;
}

export interface TeachersFilters {
  is_active?: boolean;
  school_id?: number;
  department?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface TeacherStatistics {
  teacher_id: number;
  teacher_name: string;
  current_students: number;
  current_schools: number;
  subject_distribution: Array<{
    subject: string;
    count: number;
  }>;
}

// Student assignment types
export interface StudentTeacherAssignment {
  id: number;
  student_id: number;
  teacher_id: number;
  subject?: string;
  start_date: string;
  end_date?: string;
  is_primary: boolean;
  notes?: string;
  created_date: string;
  modified_date: string;
  is_current: boolean;
  duration_description: string;
  subject_display: string;
}

export interface CreateStudentTeacherAssignmentRequest {
  student_id: number;
  teacher_id: number;
  subject?: string;
  start_date: string;
  end_date?: string;
  is_primary?: boolean;
  notes?: string;
}

// Contact method options
export const CONTACT_METHODS = [
  'Email',
  'Phone',
  'Text',
  'In-Person',
  'School System'
] as const;

export type ContactMethod = typeof CONTACT_METHODS[number];
