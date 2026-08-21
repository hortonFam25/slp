import { BaseApiService } from './base';
import type { ArchiveResponse } from './archive';

// Types for therapy sessions
export interface SessionGoal {
  id?: number;
  goal_id: number;
  planned: boolean;
  worked_on: boolean;
  priority?: number;
  pre_session_notes?: string;
  session_notes?: string;
  goal_progress_summary?: string;
  goal_met?: boolean;
  difficulty_level?: string;
  student_response?: string;
  time_spent_minutes?: number;
  created_date?: string;
  modified_date?: string;
  goal_description?: string;
  goal_category?: string;
}

export interface SessionObjective {
  id?: number;
  objective_id: number;
  goal_id: number;
  planned: boolean;
  worked_on: boolean;
  priority?: number;
  pre_session_notes?: string;
  session_notes?: string;
  trials_attempted?: number;
  trials_correct?: number;
  accuracy_percentage?: number;
  independence_level?: string;
  objective_met?: boolean;
  progress_rating?: string;
  prompt_level?: string;
  time_spent_minutes?: number;
  student_engagement?: string;
  data_collection_method?: string;
  created_date?: string;
  modified_date?: string;
  objective_description?: string;
  goal_description?: string;
  success_rate?: number;
}

export interface TherapySessionGoalsResponse {
  goals: Array<{
    goal_id: number;
    goal_text: string;
    planned: boolean;
    worked_on: boolean;
  }>;
  objectives: Array<{
    objective_id: number;
    goal_id: number;
    objective_text: string;
    planned: boolean;
    worked_on: boolean;
  }>;
}

export interface UpdateAppointmentObjectivesRequest {
  objectives: Array<{
    objective_id: number;
    goal_id: number;
    planned: boolean;
    worked_on: boolean;
    priority: number;
    pre_session_notes?: string;
  }>;
}

export interface TherapySession {
  id: number;
  student_id: number;
  appointment_id?: number;
  time_block_id?: number;
  session_date: string;
  start_time?: string;
  end_time?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  planned_duration_minutes?: number;
  actual_duration_minutes?: number;
  session_type: string;
  status: string;
  created_from?: string;
  prep_notes?: string;
  session_notes?: string;
  therapist_observations?: string;
  student_engagement?: string;
  materials_used?: string;
  goals_addressed: boolean;
  session_quality?: string;
  follow_up_needed: boolean;
  follow_up_notes?: string;
  created_date: string;
  modified_date: string;
  created_by?: string;
  
  // Computed properties
  duration_minutes: number;
  is_scheduled: boolean;
  is_group_session: boolean;
  is_active: boolean;
  is_completed: boolean;
  
  // Counts
  planned_goals_count: number;
  worked_goals_count: number;
  planned_objectives_count: number;
  worked_objectives_count: number;
  progress_entries_count: number;
  
  // Related data
  session_goals?: SessionGoal[];
  session_objectives?: SessionObjective[];
  student_name?: string;
}

export interface TherapySessionSummary {
  id: number;
  student_id: number;
  student_name?: string;
  session_date: string;
  start_time?: string;
  end_time?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  duration_minutes: number;
  session_type: string;
  status: string;
  is_scheduled: boolean;
  goals_addressed: boolean;
  session_quality?: string;
  created_date: string;
}

export interface CreateTherapySessionRequest {
  student_id: number;
  appointment_id?: number;
  time_block_id?: number;
  session_date: string;
  start_time?: string;
  end_time?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  planned_duration_minutes?: number;
  actual_duration_minutes?: number;
  session_type?: string;
  status?: string;
  created_from?: string;
  prep_notes?: string;
  session_notes?: string;
  therapist_observations?: string;
  student_engagement?: string;
  materials_used?: string;
  goals_addressed?: boolean;
  session_quality?: string;
  follow_up_needed?: boolean;
  follow_up_notes?: string;
  planned_goals?: Omit<SessionGoal, 'id' | 'created_date' | 'modified_date'>[];
  planned_objectives?: Omit<SessionObjective, 'id' | 'created_date' | 'modified_date'>[];
}

export interface UpdateTherapySessionRequest {
  start_time?: string;
  end_time?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  actual_duration_minutes?: number;
  status?: string;
  prep_notes?: string;
  session_notes?: string;
  therapist_observations?: string;
  student_engagement?: string;
  materials_used?: string;
  goals_addressed?: boolean;
  session_quality?: string;
  follow_up_needed?: boolean;
  follow_up_notes?: string;
}

export interface PlannedObjectiveForSession {
  objective_id: number;
  goal_id: number;
  priority?: number;
  pre_session_notes?: string;
}

export interface StartSessionRequest {
  student_id: number;
  session_type?: 'unscheduled' | 'link_existing' | 'create_appointment';
  appointment_id?: number;
  create_appointment?: boolean;
  planned_duration_minutes?: number;
  prep_notes?: string;
  planned_goals?: number[];
  planned_objectives?: number[];
  planned_objectives_with_notes?: PlannedObjectiveForSession[];
}

export interface CompleteSessionRequest {
  session_notes?: string;
  therapist_observations?: string;
  student_engagement?: string;
  materials_used?: string;
  goals_addressed?: boolean;
  session_quality?: string;
  follow_up_needed?: boolean;
  follow_up_notes?: string;
  create_appointment_for_unscheduled?: boolean;
}

export interface TherapySessionFilters {
  student_id?: number;
  appointment_id?: number;
  time_block_id?: number;
  session_type?: string;
  status?: string;
  created_from?: string;
  start_date?: string;
  end_date?: string;
  session_quality?: string;
  goals_addressed?: boolean;
  follow_up_needed?: boolean;
  include_goals?: boolean;
  include_objectives?: boolean;
}

export interface SessionStatistics {
  total_sessions: number;
  completed_sessions: number;
  cancelled_sessions: number;
  average_duration: number;
  goals_addressed_rate: number;
  session_quality_breakdown: Record<string, number>;
}

class TherapySessionApiService extends BaseApiService {
  constructor() {
    super('/api/therapy-sessions');
  }

  async createSession(sessionData: CreateTherapySessionRequest): Promise<TherapySession> {
    return this.post<TherapySession>('/', sessionData);
  }

  async startSession(request: StartSessionRequest): Promise<TherapySession> {
    return this.post<TherapySession>('/start', request);
  }

  async getSessions(filters?: TherapySessionFilters, skip = 0, limit = 100): Promise<TherapySessionSummary[]> {
    const params = new URLSearchParams();
    
    if (filters?.student_id) params.append('student_id', filters.student_id.toString());
    if (filters?.session_type) params.append('session_type', filters.session_type);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.start_date) params.append('start_date', filters.start_date);
    if (filters?.end_date) params.append('end_date', filters.end_date);
    if (skip > 0) params.append('skip', skip.toString());
    if (limit !== 100) params.append('limit', limit.toString());

    const query = params.toString() ? `?${params.toString()}` : '';
    return this.get<TherapySessionSummary[]>(`/${query}`);
  }

  async getSessionById(sessionId: number, includeDetails = true): Promise<TherapySession> {
    const params = includeDetails ? '?include_details=true' : '';
    return this.get<TherapySession>(`/${sessionId}${params}`);
  }

  async updateSession(sessionId: number, sessionData: UpdateTherapySessionRequest): Promise<TherapySession> {
    return this.put<TherapySession>(`/${sessionId}`, sessionData);
  }

  async completeSession(sessionId: number, request: CompleteSessionRequest): Promise<TherapySession> {
    return this.post<TherapySession>(`/${sessionId}/complete`, request);
  }

  // ARCHIVES the session. Its progress entries deliberately STAY active --
  // they are the evidence a service was delivered, and hiding the session must
  // not blank a child's progress data. See backend/app/services/archive.py.
  async deleteSession(sessionId: number): Promise<ArchiveResponse> {
    return this.delete<ArchiveResponse>(`/${sessionId}`);
  }

  async getStudentSessions(studentId: number, limit = 500): Promise<TherapySessionSummary[]> {
    const params = new URLSearchParams({
      student_id: studentId.toString(),
      limit: limit.toString(),
      skip: '0',
      order_by: 'asc'  // Get oldest sessions first
    });
    return this.get<TherapySessionSummary[]>(`/?${params.toString()}`);
  }

  async getActiveSessions(): Promise<TherapySessionSummary[]> {
    return this.get<TherapySessionSummary[]>('/active/all');
  }

  async getTherapySessionByAppointment(appointmentId: number): Promise<TherapySessionGoalsResponse> {
    return this.get<TherapySessionGoalsResponse>(`/by-appointment/${appointmentId}`);
  }

  async updateSessionObjectivesByAppointment(
    appointmentId: number,
    payload: UpdateAppointmentObjectivesRequest
  ): Promise<{ message: string }> {
    return this.put<{ message: string }>(`/by-appointment/${appointmentId}/objectives`, payload);
  }

  async getStudentSchoolYearSessions(
    studentId: number,
    startDate: string,
    endDate: string,
    limit = 75,
    anchorDate?: string
  ): Promise<TherapySession[]> {
    return this.get<TherapySession[]>(`/student/${studentId}/school-year`, {
      start_date: startDate,
      end_date: endDate,
      anchor_date: anchorDate,
      limit,
    });
  }

  async getSessionsNeedingFollowup(): Promise<TherapySessionSummary[]> {
    return this.get<TherapySessionSummary[]>('/followup/needed');
  }

  async getSessionStatistics(filters?: {
    student_id?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<SessionStatistics> {
    const params = new URLSearchParams();
    
    if (filters?.student_id) params.append('student_id', filters.student_id.toString());
    if (filters?.start_date) params.append('start_date', filters.start_date);
    if (filters?.end_date) params.append('end_date', filters.end_date);

    const query = params.toString() ? `?${params.toString()}` : '';
    return this.get<SessionStatistics>(`/statistics/summary${query}`);
  }

  async updateSessionObjective(
    sessionId: number, 
    objectiveId: number, 
    updates: Partial<SessionObjective>
  ): Promise<SessionObjective> {
    return this.put<SessionObjective>(`/${sessionId}/objectives/${objectiveId}`, updates);
  }

  async getObjectiveHistory(objectiveId: number): Promise<SessionObjective[]> {
    return this.get<SessionObjective[]>(`/objectives/${objectiveId}/history`);
  }

  async getGoalHistory(goalId: number): Promise<{ sessions: SessionObjective[], goal_info: any }> {
    return this.get<{ sessions: SessionObjective[], goal_info: any }>(`/goals/${goalId}/history`);
  }
}

export const therapySessionsApi = new TherapySessionApiService();
