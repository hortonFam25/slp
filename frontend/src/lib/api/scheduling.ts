import { BaseApiService } from './base';

// Types for scheduling entities
export interface Appointment {
  id: number;
  student_id: number;
  teacher_id?: number;
  school_id?: number;
  start_datetime: string;
  end_datetime: string;
  appointment_type: string;
  status: string;
  location?: string;
  notes?: string;
  therapy_session_completed: boolean;
  session_notes?: string;
  created_date: string;
  modified_date: string;
  created_by?: string;
  series_id?: string;
  series_metadata?: string;
}

export interface AppointmentSummary {
  id: number;
  student_id: number;
  student_name: string;
  teacher_id?: number;
  teacher_name?: string;
  school_id?: number;
  school_name?: string;
  start_datetime: string;
  end_datetime: string;
  appointment_type: string;
  status: string;
  location?: string;
  duration_minutes: number;
  series_id?: string;
}

export interface AppointmentWithDetails extends Appointment {
  student_name: string;
  teacher_name?: string;
  school_name?: string;
  duration_minutes: number;
  can_start_session: boolean;
}

export interface AppointmentCreate {
  student_id: number;
  teacher_id?: number;
  school_id?: number;
  start_datetime: string;
  end_datetime: string;
  appointment_type?: string;
  status?: string;
  location?: string;
  notes?: string;
  therapy_session_completed?: boolean;
  session_notes?: string;
  // Goal and objective planning for therapy sessions
  planned_goals?: Array<{
    goal_id: number;
    planned: boolean;
    worked_on: boolean;
    priority: number;
  }>;
  planned_objectives?: Array<{
    objective_id: number;
    goal_id: number;
    planned: boolean;
    worked_on: boolean;
    priority: number;
    pre_session_notes?: string;
  }>;
}

export interface AppointmentUpdate {
  student_id?: number;
  teacher_id?: number;
  school_id?: number;
  start_datetime?: string;
  end_datetime?: string;
  appointment_type?: string;
  status?: string;
  location?: string;
  notes?: string;
  therapy_session_completed?: boolean;
  session_notes?: string;
  // Goal and objective planning for therapy sessions
  planned_goals?: Array<{
    goal_id: number;
    planned: boolean;
    worked_on: boolean;
    priority: number;
  }>;
  planned_objectives?: Array<{
    objective_id: number;
    goal_id: number;
    planned: boolean;
    worked_on: boolean;
    priority: number;
    pre_session_notes?: string;
  }>;
}

export interface RecurringConfig {
  frequency: 'weekly' | 'monthly';
  interval: number;
  days_of_week: number[];
  end_type: 'date' | 'occurrences';
  end_date?: string;
  max_occurrences?: number;
}

export interface RecurringAppointmentCreate extends AppointmentCreate {
  recurring_config: RecurringConfig;
}

export interface RecurringAppointmentResponse {
  appointments: Appointment[];
  total_created: number;
  conflicts?: string[];
  series_id?: string;
}

export interface TimeBlock {
  id: number;
  teacher_id?: number;
  school_id?: number;
  start_datetime: string;
  end_datetime: string;
  block_type: string;
  title: string;
  max_students?: number;
  location?: string;
  notes?: string;
  status: string;
  created_date: string;
  modified_date: string;
  created_by?: string;
}

export interface TimeBlockSummary {
  id: number;
  teacher_id?: number;
  teacher_name?: string;
  school_id?: number;
  school_name?: string;
  start_datetime: string;
  end_datetime: string;
  block_type: string;
  title: string;
  max_students?: number;
  location?: string;
  status: string;
  current_student_count: number;
  available_spots: number;
  duration_minutes: number;
}

export interface TimeBlockWithStudents extends TimeBlock {
  teacher_name?: string;
  school_name?: string;
  duration_minutes: number;
  current_student_count: number;
  available_spots: number;
  is_full: boolean;
  assigned_students: StudentSummary[];
}

export interface TimeBlockCreate {
  teacher_id?: number;
  school_id?: number;
  start_datetime: string;
  end_datetime: string;
  block_type?: string;
  title: string;
  max_students?: number;
  location?: string;
  notes?: string;
  status?: string;
}

export interface TimeBlockUpdate {
  teacher_id?: number;
  school_id?: number;
  start_datetime?: string;
  end_datetime?: string;
  block_type?: string;
  title?: string;
  max_students?: number;
  location?: string;
  notes?: string;
  status?: string;
}

export interface StudentSummary {
  id: number;
  first: string;
  last: string;
  uic?: string;
  grade_level?: string;
  enrollment_status: string;
  case_manager?: string;
}

// Filter interfaces
export interface AppointmentFilters {
  start_date: string;
  end_date: string;
  student_id?: number;
  teacher_id?: number;
  school_id?: number;
  appointment_type?: string;
  status?: string;
}

export interface TimeBlockFilters {
  start_date: string;
  end_date: string;
  teacher_id?: number;
  school_id?: number;
  block_type?: string;
  status?: string;
  available_only?: boolean;
}

// Time Block Activity types
export interface TimeBlockActivity {
  id?: number;
  time_block_id: number;
  start_minute: number;
  duration_minutes: number;
  activity_name: string;
  activity_type?: string;
  description?: string;
  materials_needed?: string;
  notes?: string;
  sequence_order: number;
  created_date?: string;
  modified_date?: string;
  created_by?: string;
}

export interface TimeBlockActivityCreate {
  time_block_id: number;
  start_minute: number;
  duration_minutes: number;
  activity_name: string;
  activity_type?: string;
  description?: string;
  materials_needed?: string;
  notes?: string;
  sequence_order: number;
}

export interface TimeBlockActivityUpdate {
  start_minute?: number;
  duration_minutes?: number;
  activity_name?: string;
  activity_type?: string;
  description?: string;
  materials_needed?: string;
  notes?: string;
  sequence_order?: number;
}

// Enhanced Time Block types
export interface TimeBlockCreate {
  teacher_id?: number;
  school_id?: number;
  start_datetime: string;
  end_datetime: string;
  block_type?: string;
  title: string;
  max_students?: number;
  location?: string;
  notes?: string;
  am_pm_indicator?: string;
}

export interface TimeBlockUpdate {
  teacher_id?: number;
  school_id?: number;
  start_datetime?: string;
  end_datetime?: string;
  block_type?: string;
  title?: string;
  max_students?: number;
  location?: string;
  notes?: string;
  am_pm_indicator?: string;
}

export interface TimeBlockWithActivities extends TimeBlockWithStudents {
  activities: TimeBlockActivity[];
}

// Time Block Scheduling types
export interface TimeBlockScheduleRequest {
  time_block_id: number;
  recurring_config?: RecurringConfig;
  student_goal_assignments?: { [key: number]: { goals: number[]; objectives: number[] } };
}

export interface TimeBlockScheduleResponse {
  appointments_created: Array<{
    appointment_id: number;
    student_id: number;
    student_name: string;
    appointment_time: string;
    therapy_session_created: boolean;
    goals_planned: number;
    objectives_planned: number;
  }>;
  conflicts: Array<{
    student_id: number;
    student_name: string;
    conflict_time: string;
    reason: string;
  }>;
  total_appointments: number;
  total_conflicts: number;
  series_id?: string;
  schedule_dates: string[];
}

class SchedulingApiService extends BaseApiService {
  constructor() {
    super('/api/scheduling');
  }

  // Appointment methods
  async getAppointments(filters: AppointmentFilters): Promise<AppointmentSummary[]> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const data = await this.get<AppointmentSummary[]>(`/appointments?${params.toString()}`);
    console.log('📦 Raw appointments response:', data);
    return data;
  }

  async getAppointment(id: number): Promise<AppointmentWithDetails> {
    return this.get<AppointmentWithDetails>(`/appointments/${id}`);
  }

  async createAppointment(data: AppointmentCreate): Promise<Appointment> {
    return this.post<Appointment>('/appointments', data);
  }

  async createRecurringAppointments(data: RecurringAppointmentCreate): Promise<RecurringAppointmentResponse> {
    return this.post<RecurringAppointmentResponse>('/appointments/recurring', data);
  }

  async updateAppointment(id: number, data: AppointmentUpdate): Promise<Appointment> {
    return this.put<Appointment>(`/appointments/${id}`, data);
  }

  async deleteAppointment(id: number): Promise<void> {
    return this.delete<void>(`/appointments/${id}`);
  }

  async getStudentAppointments(
    studentId: number,
    startDate?: string,
    endDate?: string
  ): Promise<AppointmentSummary[]> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    const queryString = params.toString();
    const url = `/students/${studentId}/appointments${queryString ? `?${queryString}` : ''}`;
    
    return this.get<AppointmentSummary[]>(url);
  }

  async getAvailableSlots(
    studentId: number,
    targetDate: string,
    durationMinutes: number = 30,
    startHour: number = 8,
    endHour: number = 17
  ): Promise<{ available_slots: string[] }> {
    const params = new URLSearchParams({
      target_date: targetDate,
      duration_minutes: durationMinutes.toString(),
      start_hour: startHour.toString(),
      end_hour: endHour.toString(),
    });

    return this.get<{ available_slots: string[] }>(`/students/${studentId}/available-slots?${params.toString()}`);
  }

  // Time Block methods
  async getTimeBlocks(filters: TimeBlockFilters): Promise<TimeBlockSummary[]> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, value.toString());
      }
    });

    const data = await this.get<TimeBlockSummary[]>(`/time-blocks?${params.toString()}`);
    console.log('📦 Raw time blocks response:', data);
    return data;
  }

  async getTimeBlock(id: number): Promise<TimeBlockWithStudents> {
    return this.get<TimeBlockWithStudents>(`/time-blocks/${id}`);
  }

  async createTimeBlock(data: TimeBlockCreate): Promise<TimeBlock> {
    return this.post<TimeBlock>('/time-blocks', data);
  }

  async updateTimeBlock(id: number, data: TimeBlockUpdate): Promise<TimeBlock> {
    return this.put<TimeBlock>(`/time-blocks/${id}`, data);
  }

  async deleteTimeBlock(id: number): Promise<void> {
    return this.delete<void>(`/time-blocks/${id}`);
  }

  async assignStudentToBlock(timeBlockId: number, studentId: number): Promise<void> {
    return this.post<void>(`/time-blocks/${timeBlockId}/students/${studentId}`, {});
  }

  async removeStudentFromBlock(timeBlockId: number, studentId: number): Promise<void> {
    return this.delete<void>(`/time-blocks/${timeBlockId}/students/${studentId}`);
  }

  // Time Block Activities
  async getTimeBlockActivities(timeBlockId: number): Promise<TimeBlockActivity[]> {
    return this.get<TimeBlockActivity[]>(`/time-blocks/${timeBlockId}/activities`);
  }

  async createTimeBlockActivity(timeBlockId: number, activity: TimeBlockActivityCreate): Promise<TimeBlockActivity> {
    return this.post<TimeBlockActivity>(`/time-blocks/${timeBlockId}/activities`, activity);
  }

  async updateTimeBlockActivity(
    timeBlockId: number, 
    activityId: number, 
    activity: TimeBlockActivityUpdate
  ): Promise<TimeBlockActivity> {
    return this.put<TimeBlockActivity>(`/time-blocks/${timeBlockId}/activities/${activityId}`, activity);
  }

  async deleteTimeBlockActivity(timeBlockId: number, activityId: number): Promise<void> {
    return this.delete<void>(`/time-blocks/${timeBlockId}/activities/${activityId}`);
  }

  async reorderTimeBlockActivities(timeBlockId: number, activityOrder: number[]): Promise<void> {
    return this.put<void>(`/time-blocks/${timeBlockId}/activities/reorder`, { activity_order: activityOrder });
  }

  async getAvailableActivitySlots(timeBlockId: number, durationMinutes: number = 5): Promise<Array<{
    start_minute: number;
    end_minute: number;
    duration_minutes: number;
  }>> {
    const params = new URLSearchParams({
      duration_minutes: durationMinutes.toString()
    });
    return this.get<Array<{
      start_minute: number;
      end_minute: number;
      duration_minutes: number;
    }>>(`/time-blocks/${timeBlockId}/available-slots?${params.toString()}`);
  }

  // Time Block Scheduling
  async scheduleTimeBlock(request: TimeBlockScheduleRequest): Promise<TimeBlockScheduleResponse> {
    return this.post<TimeBlockScheduleResponse>('/time-blocks/schedule', request);
  }

  async cancelTimeBlockSchedule(timeBlockId: number, cancelFutureOnly: boolean = true): Promise<{
    cancelled_appointments: number;
    message: string;
  }> {
    const params = new URLSearchParams({
      cancel_future_only: cancelFutureOnly.toString()
    });
    return this.delete<{
      cancelled_appointments: number;
      message: string;
    }>(`/time-blocks/${timeBlockId}/schedule?${params.toString()}`);
  }

  async getTimeBlockAppointments(timeBlockId: number): Promise<Array<{
    id: number;
    student_id: number;
    student_name: string;
    start_datetime: string;
    end_datetime: string;
    status: string;
    has_therapy_session: boolean;
    session_status: string;
  }>> {
    return this.get<Array<{
      id: number;
      student_id: number;
      student_name: string;
      start_datetime: string;
      end_datetime: string;
      status: string;
      has_therapy_session: boolean;
      session_status: string;
    }>>(`/time-blocks/${timeBlockId}/appointments`);
  }

  async getTimeBlockWithActivities(timeBlockId: number): Promise<TimeBlockWithActivities> {
    return this.get<TimeBlockWithActivities>(`/time-blocks/${timeBlockId}/detailed`);
  }

  // Create Time Block with Students and Activities
  async createTimeBlockWithScheduling(data: {
    // Time block fields
    teacher_id?: number;
    school_id?: number;
    start_datetime: string;
    end_datetime: string;
    title: string;
    max_students?: number;
    location?: string;
    notes?: string;
    am_pm_indicator?: string;
    // Student assignments
    assigned_students: number[];
    // Goal/objective assignments per student
    student_goal_assignments?: { [key: number]: { goals: number[]; objectives: number[] } };
    // Activities
    activities?: TimeBlockActivity[];
    // Recurring config
    recurring_config?: RecurringConfig;
  }): Promise<{
    time_block: TimeBlock;
    schedule_result?: TimeBlockScheduleResponse;
  }> {
    // First create the time block
    const timeBlockData: TimeBlockCreate = {
      teacher_id: data.teacher_id,
      school_id: data.school_id,
      start_datetime: data.start_datetime,
      end_datetime: data.end_datetime,
      title: data.title,
      max_students: data.max_students,
      location: data.location,
      notes: data.notes,
      am_pm_indicator: data.am_pm_indicator
    };

    const timeBlock = await this.createTimeBlock(timeBlockData);

    // Add students to the time block
    for (const studentId of data.assigned_students) {
      await this.assignStudentToBlock(timeBlock.id, studentId);
    }

    // Add activities if provided
    if (data.activities && data.activities.length > 0) {
      for (const activity of data.activities) {
        const activityData: TimeBlockActivityCreate = {
          time_block_id: timeBlock.id,
          start_minute: activity.start_minute,
          duration_minutes: activity.duration_minutes,
          activity_name: activity.activity_name,
          activity_type: activity.activity_type,
          description: activity.description,
          materials_needed: activity.materials_needed,
          notes: activity.notes,
          sequence_order: activity.sequence_order
        };
        await this.createTimeBlockActivity(timeBlock.id, activityData);
      }
    }

    // Schedule the time block (create appointments)
    let scheduleResult: TimeBlockScheduleResponse | undefined;
    const scheduleRequest: TimeBlockScheduleRequest = {
      time_block_id: timeBlock.id,
      recurring_config: data.recurring_config,
      student_goal_assignments: data.student_goal_assignments
    };

    try {
      scheduleResult = await this.scheduleTimeBlock(scheduleRequest);
    } catch (error) {
      console.warn('Failed to schedule time block appointments:', error);
    }

    return {
      time_block: timeBlock,
      schedule_result: scheduleResult
    };
  }
}

// Export singleton instance
export const schedulingApi = new SchedulingApiService();
