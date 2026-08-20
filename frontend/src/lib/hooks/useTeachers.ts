import { useState, useEffect, useCallback } from 'react';
import { teachersApi } from '../api/teachers';
import type {
  Teacher,
  TeacherSummary,
  CreateTeacherRequest,
  UpdateTeacherRequest,
  TeachersFilters,
  TeacherStatistics,
  SupportStaffRole
} from '../api/types/teachers';
import type {
  TeacherSchoolAssignment,
  CreateTeacherSchoolAssignmentRequest
} from '../api/types/schools';

interface UseTeachersState {
  teachers: Teacher[];
  teachersSummary: TeacherSummary[];
  loading: boolean;
  error: string | null;
  departments: string[];
}

interface UseTeachersActions {
  fetchTeachers: (filters?: TeachersFilters) => Promise<void>;
  fetchTeachersSummary: (activeOnly?: boolean, schoolId?: number) => Promise<void>;
  fetchDepartments: () => Promise<void>;
  createTeacher: (teacher: CreateTeacherRequest) => Promise<Teacher>;
  updateTeacher: (teacherId: number, updates: UpdateTeacherRequest) => Promise<Teacher>;
  deleteTeacher: (teacherId: number) => Promise<void>;
  getTeacher: (teacherId: number) => Promise<Teacher>;
  getTeacherStatistics: (teacherId: number) => Promise<TeacherStatistics>;
  getRoles: (activeOnly?: boolean) => Promise<SupportStaffRole[]>;
  getTeachersBySchool: (schoolId: number, currentOnly?: boolean) => Promise<TeacherSummary[]>;
  // Teacher-School Assignment methods
  getTeacherSchoolAssignments: (teacherId: number) => Promise<TeacherSchoolAssignment[]>;
  createTeacherSchoolAssignment: (assignment: CreateTeacherSchoolAssignmentRequest) => Promise<TeacherSchoolAssignment>;
  updateTeacherSchoolAssignment: (assignmentId: number, updates: Partial<CreateTeacherSchoolAssignmentRequest>) => Promise<TeacherSchoolAssignment>;
  deleteTeacherSchoolAssignment: (assignmentId: number) => Promise<void>;
  refreshTeachers: () => Promise<void>;
  clearError: () => void;
}

export function useTeachers(initialFilters?: TeachersFilters): UseTeachersState & UseTeachersActions {
  const [state, setState] = useState<UseTeachersState>({
    teachers: [],
    teachersSummary: [],
    loading: false,
    error: null,
    departments: []
  });

  const [currentFilters, setCurrentFilters] = useState<TeachersFilters | undefined>(initialFilters);

  const setLoading = useCallback((loading: boolean) => {
    setState(prev => ({ ...prev, loading }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState(prev => ({ ...prev, error }));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, [setError]);

  const fetchTeachers = useCallback(async (filters?: TeachersFilters) => {
    try {
      setLoading(true);
      setError(null);
      setCurrentFilters(filters);
      const teachers = await teachersApi.getTeachers(filters);
      setState(prev => ({ ...prev, teachers }));
    } catch (error) {
      console.error('Error fetching teachers:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch teachers');
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError]);

  const fetchTeachersSummary = useCallback(async (activeOnly = true, schoolId?: number) => {
    try {
      setError(null);
      const teachersSummary = await teachersApi.getTeachersSummary(activeOnly, schoolId);
      setState(prev => ({ ...prev, teachersSummary }));
    } catch (error) {
      console.error('Error fetching teachers summary:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch teachers summary');
    }
  }, [setError]);

  const fetchDepartments = useCallback(async () => {
    try {
      const departments = await teachersApi.getDepartments();
      setState(prev => ({ ...prev, departments }));
    } catch (error) {
      console.error('Error fetching departments:', error);
      setError(error instanceof Error ? error.message : 'Failed to fetch departments');
    }
  }, [setError]);

  const createTeacher = useCallback(async (teacher: CreateTeacherRequest): Promise<Teacher> => {
    try {
      setError(null);
      const newTeacher = await teachersApi.createTeacher(teacher);
      setState(prev => ({ ...prev, teachers: [...prev.teachers, newTeacher] }));
      return newTeacher;
    } catch (error) {
      console.error('Error creating teacher:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create teacher';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateTeacher = useCallback(async (teacherId: number, updates: UpdateTeacherRequest): Promise<Teacher> => {
    try {
      setError(null);
      const updatedTeacher = await teachersApi.updateTeacher(teacherId, updates);
      setState(prev => ({
        ...prev,
        teachers: prev.teachers.map(teacher => teacher.id === teacherId ? updatedTeacher : teacher)
      }));
      return updatedTeacher;
    } catch (error) {
      console.error('Error updating teacher:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update teacher';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteTeacher = useCallback(async (teacherId: number): Promise<void> => {
    try {
      setError(null);
      await teachersApi.deleteTeacher(teacherId);
      setState(prev => ({
        ...prev,
        teachers: prev.teachers.map(teacher => 
          teacher.id === teacherId ? { ...teacher, is_active: false } : teacher
        )
      }));
    } catch (error) {
      console.error('Error deleting teacher:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete teacher';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getTeacher = useCallback(async (teacherId: number): Promise<Teacher> => {
    try {
      setError(null);
      return await teachersApi.getTeacher(teacherId);
    } catch (error) {
      console.error('Error fetching teacher:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch teacher';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getTeacherStatistics = useCallback(async (teacherId: number): Promise<TeacherStatistics> => {
    try {
      setError(null);
      return await teachersApi.getTeacherStatistics(teacherId);
    } catch (error) {
      console.error('Error fetching teacher statistics:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch teacher statistics';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getRoles = useCallback(async (activeOnly = true): Promise<SupportStaffRole[]> => {
    try {
      setError(null);
      return await teachersApi.getRoles(activeOnly);
    } catch (error) {
      console.error('Error fetching support staff roles:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch support staff roles';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getTeachersBySchool = useCallback(async (schoolId: number, currentOnly = true): Promise<TeacherSummary[]> => {
    try {
      setError(null);
      return await teachersApi.getTeachersBySchool(schoolId, currentOnly);
    } catch (error) {
      console.error('Error fetching teachers by school:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch teachers by school';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const getTeacherSchoolAssignments = useCallback(async (teacherId: number): Promise<TeacherSchoolAssignment[]> => {
    try {
      setError(null);
      return await teachersApi.getTeacherSchoolAssignments(teacherId);
    } catch (error) {
      console.error('Error fetching teacher school assignments:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch teacher school assignments';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const createTeacherSchoolAssignment = useCallback(async (assignment: CreateTeacherSchoolAssignmentRequest): Promise<TeacherSchoolAssignment> => {
    try {
      setError(null);
      return await teachersApi.createTeacherSchoolAssignment(assignment);
    } catch (error) {
      console.error('Error creating teacher school assignment:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create teacher school assignment';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const updateTeacherSchoolAssignment = useCallback(async (assignmentId: number, updates: Partial<CreateTeacherSchoolAssignmentRequest>): Promise<TeacherSchoolAssignment> => {
    try {
      setError(null);
      return await teachersApi.updateTeacherSchoolAssignment(assignmentId, updates);
    } catch (error) {
      console.error('Error updating teacher school assignment:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update teacher school assignment';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const deleteTeacherSchoolAssignment = useCallback(async (assignmentId: number): Promise<void> => {
    try {
      setError(null);
      await teachersApi.deleteTeacherSchoolAssignment(assignmentId);
    } catch (error) {
      console.error('Error deleting teacher school assignment:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete teacher school assignment';
      setError(errorMessage);
      throw error;
    }
  }, [setError]);

  const refreshTeachers = useCallback(async () => {
    if (currentFilters) {
      await fetchTeachers(currentFilters);
    }
  }, [fetchTeachers, currentFilters]);

  // Load initial data
  useEffect(() => {
    if (initialFilters) {
      fetchTeachers(initialFilters);
    }
    fetchDepartments();
  }, [fetchTeachers, fetchDepartments, initialFilters]);

  return {
    ...state,
    fetchTeachers,
    fetchTeachersSummary,
    fetchDepartments,
    createTeacher,
    updateTeacher,
    deleteTeacher,
    getTeacher,
    getTeacherStatistics,
    getRoles,
    getTeachersBySchool,
    getTeacherSchoolAssignments,
    createTeacherSchoolAssignment,
    updateTeacherSchoolAssignment,
    deleteTeacherSchoolAssignment,
    refreshTeachers,
    clearError,
  };
}
