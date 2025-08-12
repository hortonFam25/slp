import { useQuery, useMutation, useQueryClient, UseQueryResult } from '@tanstack/react-query';
import { 
  therapySessionsApi, 
  TherapySession, 
  TherapySessionSummary, 
  CreateTherapySessionRequest, 
  UpdateTherapySessionRequest,
  StartSessionRequest, 
  CompleteSessionRequest,
  TherapySessionFilters,
  SessionStatistics
} from '../api/therapySessions';

// Query keys for therapy sessions
export const THERAPY_SESSION_QUERY_KEYS = {
  all: ['therapy-sessions'] as const,
  lists: () => [...THERAPY_SESSION_QUERY_KEYS.all, 'list'] as const,
  list: (filters?: TherapySessionFilters) => [...THERAPY_SESSION_QUERY_KEYS.lists(), filters] as const,
  details: () => [...THERAPY_SESSION_QUERY_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...THERAPY_SESSION_QUERY_KEYS.details(), id] as const,
  student: (studentId: number) => [...THERAPY_SESSION_QUERY_KEYS.all, 'student', studentId] as const,
  active: () => [...THERAPY_SESSION_QUERY_KEYS.all, 'active'] as const,
  followup: () => [...THERAPY_SESSION_QUERY_KEYS.all, 'followup'] as const,
  statistics: (filters?: { student_id?: number; start_date?: string; end_date?: string }) => 
    [...THERAPY_SESSION_QUERY_KEYS.all, 'statistics', filters] as const,
};

// Hook to get therapy sessions with filters
export function useTherapySessions(
  filters?: TherapySessionFilters,
  options?: {
    skip?: number;
    limit?: number;
    enabled?: boolean;
  }
): UseQueryResult<TherapySessionSummary[]> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.list(filters),
    queryFn: () => therapySessionsApi.getSessions(filters, options?.skip, options?.limit),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Hook to get a specific therapy session by ID
export function useTherapySession(
  sessionId: number,
  includeDetails = true,
  enabled = true
): UseQueryResult<TherapySession> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.detail(sessionId),
    queryFn: () => therapySessionsApi.getSessionById(sessionId, includeDetails),
    enabled: enabled && !!sessionId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

// Hook to get therapy sessions for a specific student
export function useStudentTherapySessions(
  studentId: number,
  limit = 50,
  enabled = true
): UseQueryResult<TherapySessionSummary[]> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.student(studentId),
    queryFn: () => therapySessionsApi.getStudentSessions(studentId, limit),
    enabled: enabled && !!studentId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Hook to get currently active therapy sessions
export function useActiveTherapySessions(enabled = true): UseQueryResult<TherapySessionSummary[]> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.active(),
    queryFn: () => therapySessionsApi.getActiveSessions(),
    enabled,
    refetchInterval: 30 * 1000, // Refresh every 30 seconds for active sessions
    staleTime: 0, // Always consider stale for real-time updates
  });
}

// Hook to get sessions needing follow-up
export function useSessionsNeedingFollowup(enabled = true): UseQueryResult<TherapySessionSummary[]> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.followup(),
    queryFn: () => therapySessionsApi.getSessionsNeedingFollowup(),
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

// Hook to get therapy session statistics
export function useTherapySessionStatistics(
  filters?: { student_id?: number; start_date?: string; end_date?: string },
  enabled = true
): UseQueryResult<SessionStatistics> {
  return useQuery({
    queryKey: THERAPY_SESSION_QUERY_KEYS.statistics(filters),
    queryFn: () => therapySessionsApi.getSessionStatistics(filters),
    enabled,
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

// Hook to create a new therapy session
export function useCreateTherapySession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (sessionData: CreateTherapySessionRequest) => 
      therapySessionsApi.createSession(sessionData),
    onSuccess: (newSession) => {
      // Invalidate and refetch relevant queries
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.student(newSession.student_id) });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.statistics() });
      
      // If linked to appointment, invalidate scheduling queries
      if (newSession.appointment_id) {
        queryClient.invalidateQueries({ queryKey: ['appointments'] });
      }
    },
  });
}

// Hook to start a therapy session
export function useStartTherapySession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: StartSessionRequest) => 
      therapySessionsApi.startSession(request),
    onSuccess: (newSession) => {
      // Invalidate and refetch relevant queries
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.student(newSession.student_id) });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.active() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.statistics() });
      
      // If linked to appointment, invalidate scheduling queries
      if (newSession.appointment_id) {
        queryClient.invalidateQueries({ queryKey: ['appointments'] });
      }
    },
  });
}

// Hook to update a therapy session
export function useUpdateTherapySession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ sessionId, sessionData }: { sessionId: number; sessionData: UpdateTherapySessionRequest }) =>
      therapySessionsApi.updateSession(sessionId, sessionData),
    onSuccess: (updatedSession, { sessionId }) => {
      // Update the specific session in cache
      queryClient.setQueryData(
        THERAPY_SESSION_QUERY_KEYS.detail(sessionId),
        updatedSession
      );
      
      // Invalidate list queries to ensure consistency
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.student(updatedSession.student_id) });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.active() });
    },
  });
}

// Hook to complete a therapy session
export function useCompleteTherapySession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ sessionId, request }: { sessionId: number; request: CompleteSessionRequest }) =>
      therapySessionsApi.completeSession(sessionId, request),
    onSuccess: (completedSession, { sessionId }) => {
      // Update the specific session in cache
      queryClient.setQueryData(
        THERAPY_SESSION_QUERY_KEYS.detail(sessionId),
        completedSession
      );
      
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.student(completedSession.student_id) });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.active() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.statistics() });
      
      if (completedSession.follow_up_needed) {
        queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.followup() });
      }
      
      // If linked to appointment, invalidate scheduling queries
      if (completedSession.appointment_id) {
        queryClient.invalidateQueries({ queryKey: ['appointments'] });
      }
    },
  });
}

// Hook to delete a therapy session
export function useDeleteTherapySession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (sessionId: number) => therapySessionsApi.deleteSession(sessionId),
    onSuccess: (_, sessionId) => {
      // Remove the specific session from cache
      queryClient.removeQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.detail(sessionId) });
      
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() });
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.all });
    },
  });
}

// Utility hook for invalidating therapy session queries
export function useInvalidateTherapySessions() {
  const queryClient = useQueryClient();
  
  return {
    invalidateAll: () => queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.all }),
    invalidateLists: () => queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.lists() }),
    invalidateStudent: (studentId: number) => 
      queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.student(studentId) }),
    invalidateActive: () => queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.active() }),
    invalidateStatistics: () => queryClient.invalidateQueries({ queryKey: THERAPY_SESSION_QUERY_KEYS.statistics() }),
  };
}
