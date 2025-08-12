import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentsApi, StudentsFilters, CreateStudentRequest, UpdateStudentRequest } from '../../api';

// Query keys for React Query caching
export const STUDENTS_QUERY_KEYS = {
  all: ['students'] as const,
  lists: () => [...STUDENTS_QUERY_KEYS.all, 'list'] as const,
  list: (filters?: StudentsFilters) => [...STUDENTS_QUERY_KEYS.lists(), filters] as const,
  details: () => [...STUDENTS_QUERY_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...STUDENTS_QUERY_KEYS.details(), id] as const,
  byUic: (uic: string) => [...STUDENTS_QUERY_KEYS.all, 'uic', uic] as const,
} as const;

// Hooks for querying students
export function useStudentsQuery(filters?: StudentsFilters) {
  return useQuery({
    queryKey: STUDENTS_QUERY_KEYS.list(filters),
    queryFn: () => studentsApi.getStudents(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useStudentQuery(id: number, enabled = true) {
  return useQuery({
    queryKey: STUDENTS_QUERY_KEYS.detail(id),
    queryFn: () => studentsApi.getStudent(id),
    enabled: enabled && id > 0,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useStudentByUicQuery(uic: string, enabled = true) {
  return useQuery({
    queryKey: STUDENTS_QUERY_KEYS.byUic(uic),
    queryFn: () => studentsApi.getStudentByUic(uic),
    enabled: enabled && !!uic,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Hooks for mutating students
export function useCreateStudentMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateStudentRequest) => studentsApi.createStudent(data),
    onSuccess: (newStudent) => {
      // Invalidate and refetch students lists
      queryClient.invalidateQueries({ queryKey: STUDENTS_QUERY_KEYS.lists() });
      
      // Add the new student to the cache
      queryClient.setQueryData(
        STUDENTS_QUERY_KEYS.detail(newStudent.id),
        newStudent
      );
    },
  });
}

export function useUpdateStudentMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateStudentRequest }) => 
      studentsApi.updateStudent(id, data),
    onSuccess: (updatedStudent, { id }) => {
      // Update the student in cache
      queryClient.setQueryData(
        STUDENTS_QUERY_KEYS.detail(id),
        updatedStudent
      );
      
      // Invalidate lists to refresh summaries
      queryClient.invalidateQueries({ queryKey: STUDENTS_QUERY_KEYS.lists() });
    },
  });
}

export function useDeleteStudentMutation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => studentsApi.deleteStudent(id),
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: STUDENTS_QUERY_KEYS.detail(id) });
      
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: STUDENTS_QUERY_KEYS.lists() });
    },
  });
}

// Convenience hooks for common use cases
export function useActiveStudentsQuery() {
  return useStudentsQuery({ enrollment_status: 'Active' });
}

export function useStudentsByCaseManagerQuery(caseManager: string, enabled = true) {
  return useStudentsQuery(
    enabled && caseManager ? { case_manager: caseManager } : undefined
  );
}
