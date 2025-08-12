import { useQuery } from '@tanstack/react-query';
import { schedulingStudentsApi, StudentScheduleView, StudentScheduleFilters } from '../api/schedulingStudents';

export function useSchedulingStudents(filters?: StudentScheduleFilters) {
  const queryKey = ['scheduling-students', filters];
  
  const {
    data: students = [],
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey,
    queryFn: async () => {
      console.log('🔍 Fetching scheduling students with filters:', filters);
      try {
        const result = await schedulingStudentsApi.getStudentsForScheduling(filters);
        console.log('✅ Scheduling students fetched successfully:', result);
        return result;
      } catch (error) {
        console.error('❌ Error fetching scheduling students:', error);
        throw error;
      }
    },
    enabled: true, // Always enabled since we want to fetch students
    retry: 1,
    staleTime: 30000 // 30 seconds - fresher data for scheduling
  });

  const errorMessage = queryError instanceof Error ? queryError.message : '';
  console.log('📊 Scheduling students hook state:', { 
    loading, 
    error: errorMessage, 
    dataLength: students?.length || 0,
    filters 
  });

  return {
    students,
    loading,
    error: errorMessage,
    refetch
  };
}

export function useSchedulingStudent(studentId?: number) {
  const queryKey = ['scheduling-student', studentId];
  
  const {
    data: student,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey,
    queryFn: () => schedulingStudentsApi.getStudentForScheduling(studentId!),
    enabled: !!studentId && studentId > 0,
    retry: 1,
    staleTime: 30000
  });

  const errorMessage = queryError instanceof Error ? queryError.message : '';

  return {
    student,
    loading,
    error: errorMessage,
    refetch
  };
}
