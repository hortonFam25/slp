import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  schedulingApi, 
  AppointmentFilters, 
  TimeBlockFilters,
  AppointmentCreate,
  AppointmentUpdate,
  TimeBlockCreate,
  TimeBlockUpdate,
  AppointmentSummary,
  TimeBlockSummary,
  AppointmentWithDetails,
  TimeBlockWithStudents
} from '../api/scheduling';

// Appointments hook
export function useAppointments(filters?: AppointmentFilters) {
  const {
    data: appointments,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['appointments', filters],
    queryFn: async () => {
      if (!filters) return [];
      try {
        console.log('🔍 Fetching appointments with filters:', filters);
        const result = await schedulingApi.getAppointments(filters);
        console.log('✅ Appointments fetched successfully:', result);
        return result;
      } catch (error) {
        console.error('❌ Error fetching appointments:', error);
        throw error;
      }
    },
    enabled: !!filters,
    retry: 1, // Reduce retries to avoid cached errors
    staleTime: 0 // Force fresh data
  });

  const errorMessage = queryError instanceof Error ? queryError.message : '';
  console.log('📊 Appointments hook state:', { loading, error: errorMessage, dataLength: appointments?.length || 0 });

  return {
    appointments: appointments || [],
    loading,
    error: errorMessage,
    refetch
  };
}

// Single appointment hook
export function useAppointment(appointmentId?: number) {
  const [error, setError] = useState<string>('');

  const {
    data: appointment,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['appointment', appointmentId],
    queryFn: () => appointmentId ? schedulingApi.getAppointment(appointmentId) : Promise.resolve(null),
    enabled: !!appointmentId,
    onError: (err: Error) => setError(err.message)
  });

  return {
    appointment,
    loading,
    error: error || queryError?.message || '',
    refetch
  };
}

// Appointment mutations hook
export function useAppointmentMutations() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string>('');

  const createMutation = useMutation({
    mutationFn: (data: AppointmentCreate) => schedulingApi.createAppointment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AppointmentUpdate }) => 
      schedulingApi.updateAppointment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['appointment'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => schedulingApi.deleteAppointment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const createAppointment = useCallback(async (data: AppointmentCreate) => {
    try {
      return await createMutation.mutateAsync(data);
    } catch (err) {
      throw err;
    }
  }, [createMutation]);

  const updateAppointment = useCallback(async (id: number, data: AppointmentUpdate) => {
    try {
      return await updateMutation.mutateAsync({ id, data });
    } catch (err) {
      throw err;
    }
  }, [updateMutation]);

  const deleteAppointment = useCallback(async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      throw err;
    }
  }, [deleteMutation]);

  return {
    createAppointment,
    updateAppointment,
    deleteAppointment,
    loading: createMutation.isPending || updateMutation.isPending || deleteMutation.isPending,
    error
  };
}

// Time blocks hook
export function useTimeBlocks(filters?: TimeBlockFilters) {
  const {
    data: timeBlocks,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['timeBlocks', filters],
    queryFn: async () => {
      if (!filters) return [];
      try {
        console.log('🔍 Fetching time blocks with filters:', filters);
        const result = await schedulingApi.getTimeBlocks(filters);
        console.log('✅ Time blocks fetched successfully:', result);
        return result;
      } catch (error) {
        console.error('❌ Error fetching time blocks:', error);
        throw error;
      }
    },
    enabled: !!filters,
    retry: 1, // Reduce retries to avoid cached errors
    staleTime: 0 // Force fresh data
  });

  const errorMessage = queryError instanceof Error ? queryError.message : '';
  console.log('📊 Time blocks hook state:', { loading, error: errorMessage, dataLength: timeBlocks?.length || 0 });

  return {
    timeBlocks: timeBlocks || [],
    loading,
    error: errorMessage,
    refetch
  };
}

// Single time block hook
export function useTimeBlock(timeBlockId?: number) {
  const [error, setError] = useState<string>('');

  const {
    data: timeBlock,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['timeBlock', timeBlockId],
    queryFn: () => timeBlockId ? schedulingApi.getTimeBlock(timeBlockId) : Promise.resolve(null),
    enabled: !!timeBlockId,
    onError: (err: Error) => setError(err.message)
  });

  return {
    timeBlock,
    loading,
    error: error || queryError?.message || '',
    refetch
  };
}

// Time block mutations hook
export function useTimeBlockMutations() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string>('');

  const createMutation = useMutation({
    mutationFn: (data: TimeBlockCreate) => schedulingApi.createTimeBlock(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeBlocks'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: TimeBlockUpdate }) => 
      schedulingApi.updateTimeBlock(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeBlocks'] });
      queryClient.invalidateQueries({ queryKey: ['timeBlock'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => schedulingApi.deleteTimeBlock(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeBlocks'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const assignStudentMutation = useMutation({
    mutationFn: ({ timeBlockId, studentId }: { timeBlockId: number; studentId: number }) => 
      schedulingApi.assignStudentToBlock(timeBlockId, studentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeBlocks'] });
      queryClient.invalidateQueries({ queryKey: ['timeBlock'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const removeStudentMutation = useMutation({
    mutationFn: ({ timeBlockId, studentId }: { timeBlockId: number; studentId: number }) => 
      schedulingApi.removeStudentFromBlock(timeBlockId, studentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['timeBlocks'] });
      queryClient.invalidateQueries({ queryKey: ['timeBlock'] });
      setError('');
    },
    onError: (err: Error) => setError(err.message)
  });

  const createTimeBlock = useCallback(async (data: TimeBlockCreate) => {
    try {
      return await createMutation.mutateAsync(data);
    } catch (err) {
      throw err;
    }
  }, [createMutation]);

  const updateTimeBlock = useCallback(async (id: number, data: TimeBlockUpdate) => {
    try {
      return await updateMutation.mutateAsync({ id, data });
    } catch (err) {
      throw err;
    }
  }, [updateMutation]);

  const deleteTimeBlock = useCallback(async (id: number) => {
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      throw err;
    }
  }, [deleteMutation]);

  const assignStudentToBlock = useCallback(async (timeBlockId: number, studentId: number) => {
    try {
      await assignStudentMutation.mutateAsync({ timeBlockId, studentId });
    } catch (err) {
      throw err;
    }
  }, [assignStudentMutation]);

  const removeStudentFromBlock = useCallback(async (timeBlockId: number, studentId: number) => {
    try {
      await removeStudentMutation.mutateAsync({ timeBlockId, studentId });
    } catch (err) {
      throw err;
    }
  }, [removeStudentMutation]);

  return {
    createTimeBlock,
    updateTimeBlock,
    deleteTimeBlock,
    assignStudentToBlock,
    removeStudentFromBlock,
    loading: (
      createMutation.isPending || 
      updateMutation.isPending || 
      deleteMutation.isPending ||
      assignStudentMutation.isPending ||
      removeStudentMutation.isPending
    ),
    error
  };
}

// Student appointments hook
export function useStudentAppointments(studentId?: number, startDate?: string, endDate?: string) {
  const [error, setError] = useState<string>('');

  const {
    data: appointments,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['studentAppointments', studentId, startDate, endDate],
    queryFn: () => studentId ? schedulingApi.getStudentAppointments(studentId, startDate, endDate) : Promise.resolve([]),
    enabled: !!studentId,
    onError: (err: Error) => setError(err.message)
  });

  return {
    appointments: appointments || [],
    loading,
    error: error || queryError?.message || '',
    refetch
  };
}

// Available time slots hook
export function useAvailableSlots(
  studentId?: number,
  targetDate?: string,
  durationMinutes: number = 30,
  startHour: number = 8,
  endHour: number = 17
) {
  const [error, setError] = useState<string>('');

  const {
    data: slotsData,
    isLoading: loading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['availableSlots', studentId, targetDate, durationMinutes, startHour, endHour],
    queryFn: () => studentId && targetDate ? 
      schedulingApi.getAvailableSlots(studentId, targetDate, durationMinutes, startHour, endHour) : 
      Promise.resolve({ available_slots: [] }),
    enabled: !!(studentId && targetDate),
    onError: (err: Error) => setError(err.message)
  });

  return {
    availableSlots: slotsData?.available_slots || [],
    loading,
    error: error || queryError?.message || '',
    refetch
  };
}
