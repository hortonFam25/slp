// Global API types and interfaces

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  message?: string;
}

export interface ApiError {
  message: string;
  status: number;
  details?: any;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
  hasNext: boolean;
  hasPrev: boolean;
}

// Common query parameters
export interface BaseQueryParams {
  page?: number;
  limit?: number;
  sort?: string;
  order?: 'asc' | 'desc';
}

// API endpoints configuration
export const API_ENDPOINTS = {
  // Health
  HEALTH: '/api/health',
  
  // Students
  STUDENTS: '/api/students',
  STUDENTS_BY_ID: (id: number) => `/api/students/${id}`,
  STUDENTS_BY_UIC: (uic: string) => `/api/students/uic/${uic}`,
  
  // Future endpoints
  GOALS: '/api/goals',
  ASSESSMENTS: '/api/assessments',
  PROGRESS: '/api/progress',
  SERVICES: '/api/services',
  ELIGIBILITIES: '/api/eligibilities',
} as const;
