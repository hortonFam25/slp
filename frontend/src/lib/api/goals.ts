import { BaseApiService } from './base';
import type { ArchiveResponse } from './archive';
import type {
  IEPGoal,
  IEPGoalSummary,
  IEPGoalWithObjectives,
  GoalObjective,
  ObjectiveProgressEntry,
  GoalCategory,
  CreateGoalRequest,
  UpdateGoalRequest,
  CreateObjectiveRequest,
  UpdateObjectiveRequest,
  CreateProgressEntryRequest,
  UpdateProgressEntryRequest,
  GoalsFilters,
  ObjectivesFilters,
  ProgressEntriesFilters
} from './types/goals';

class GoalsApiService extends BaseApiService {
  constructor() {
    super('/api'); // Set the base URL for all goal-related endpoints
  }

  // Goal Categories
  async getGoalCategories(activeOnly: boolean = false): Promise<GoalCategory[]> {
    const params = activeOnly ? '?active_only=true' : '?active_only=false';
    return this.get<GoalCategory[]>(`/goal-categories${params}`);
  }

  async getGoalCategory(categoryId: number): Promise<GoalCategory> {
    return this.get<GoalCategory>(`/goal-categories/${categoryId}`);
  }

  async createGoalCategory(categoryData: Omit<GoalCategory, 'id' | 'created_date'>): Promise<GoalCategory> {
    return this.post<GoalCategory>('/goal-categories', categoryData);
  }

  async updateGoalCategory(categoryId: number, categoryData: Partial<Omit<GoalCategory, 'id' | 'created_date'>>): Promise<GoalCategory> {
    return this.put<GoalCategory>(`/goal-categories/${categoryId}`, categoryData);
  }

  async deleteGoalCategory(categoryId: number): Promise<void> {
    return this.delete(`/goal-categories/${categoryId}`);
  }

  // IEP Goals
  async getGoals(filters?: GoalsFilters): Promise<IEPGoal[]> {
    const params = new URLSearchParams();
    if (filters?.student_id) params.append('student_id', filters.student_id.toString());
    if (filters?.goal_status) params.append('goal_status', filters.goal_status);
    if (filters?.goal_category_id) params.append('goal_category_id', filters.goal_category_id.toString());
    if (filters?.start_date_from) params.append('start_date_from', filters.start_date_from);
    if (filters?.start_date_to) params.append('start_date_to', filters.start_date_to);

    const queryString = params.toString();
    return this.get<IEPGoal[]>(`/goals${queryString ? `?${queryString}` : ''}`);
  }

  async getGoal(goalId: number): Promise<IEPGoal> {
    return this.get<IEPGoal>(`/goals/${goalId}`);
  }

  async getGoalWithObjectives(goalId: number): Promise<IEPGoal> {
    return this.get<IEPGoal>(`/goals/${goalId}/with-objectives`);
  }

  async getStudentGoals(studentId: number): Promise<IEPGoal[]> {
    return this.get<IEPGoal[]>(`/students/${studentId}/goals`);
  }

  async getStudentGoalsSummary(studentId: number): Promise<IEPGoalSummary[]> {
    return this.get<IEPGoalSummary[]>(`/students/${studentId}/goals/summary`);
  }

  async getStudentActiveGoals(studentId: number): Promise<IEPGoalWithObjectives[]> {
    return this.get<IEPGoalWithObjectives[]>(`/students/${studentId}/goals/active`);
  }

  async createGoal(goal: CreateGoalRequest): Promise<IEPGoal> {
    return this.post<IEPGoal>('/goals', goal);
  }

  async updateGoal(goalId: number, updates: UpdateGoalRequest): Promise<IEPGoal> {
    return this.put<IEPGoal>(`/goals/${goalId}`, updates);
  }

  // ARCHIVES the goal with its objectives and their progress entries. Same
  // verb, same path -- the backend stopped deleting. The response carries
  // `archiveEventId`, which is what an undo is built from.
  async deleteGoal(goalId: number): Promise<ArchiveResponse> {
    return this.delete<ArchiveResponse>(`/goals/${goalId}`);
  }

  // Goal Objectives
  async getObjectives(filters?: ObjectivesFilters): Promise<GoalObjective[]> {
    const params = new URLSearchParams();
    if (filters?.goal_id) params.append('goal_id', filters.goal_id.toString());
    if (filters?.progress_status) params.append('progress_status', filters.progress_status);
    if (filters?.schedule_frequency) params.append('schedule_frequency', filters.schedule_frequency);

    const queryString = params.toString();
    return this.get<GoalObjective[]>(`/objectives${queryString ? `?${queryString}` : ''}`);
  }

  async getObjective(objectiveId: number): Promise<GoalObjective> {
    return this.get<GoalObjective>(`/objectives/${objectiveId}`);
  }

  async getObjectiveWithProgress(objectiveId: number): Promise<GoalObjective> {
    return this.get<GoalObjective>(`/objectives/${objectiveId}/with-progress`);
  }

  async getGoalObjectives(goalId: number): Promise<GoalObjective[]> {
    return this.get<GoalObjective[]>(`/goals/${goalId}/objectives`);
  }

  async createObjective(objective: CreateObjectiveRequest): Promise<GoalObjective> {
    return this.post<GoalObjective>('/objectives', objective);
  }

  async updateObjective(objectiveId: number, updates: UpdateObjectiveRequest): Promise<GoalObjective> {
    return this.put<GoalObjective>(`/objectives/${objectiveId}`, updates);
  }

  // ARCHIVES the objective with its progress entries.
  async deleteObjective(objectiveId: number): Promise<ArchiveResponse> {
    return this.delete<ArchiveResponse>(`/objectives/${objectiveId}`);
  }

  // Progress Entries
  async getProgressEntries(filters?: ProgressEntriesFilters): Promise<ObjectiveProgressEntry[]> {
    const params = new URLSearchParams();
    if (filters?.objective_id) params.append('objective_id', filters.objective_id.toString());
    if (filters?.progress_date_from) params.append('progress_date_from', filters.progress_date_from);
    if (filters?.progress_date_to) params.append('progress_date_to', filters.progress_date_to);
    if (filters?.therapist_initials) params.append('therapist_initials', filters.therapist_initials);

    const queryString = params.toString();
    return this.get<ObjectiveProgressEntry[]>(`/progress-entries${queryString ? `?${queryString}` : ''}`);
  }

  async getProgressEntry(entryId: number): Promise<ObjectiveProgressEntry> {
    return this.get<ObjectiveProgressEntry>(`/progress-entries/${entryId}`);
  }

  async getObjectiveProgressEntries(objectiveId: number): Promise<ObjectiveProgressEntry[]> {
    return this.get<ObjectiveProgressEntry[]>(`/objectives/${objectiveId}/progress-entries`);
  }

  async createProgressEntry(entry: CreateProgressEntryRequest): Promise<ObjectiveProgressEntry> {
    return this.post<ObjectiveProgressEntry>('/progress-entries', entry);
  }

  async updateProgressEntry(entryId: number, updates: UpdateProgressEntryRequest): Promise<ObjectiveProgressEntry> {
    return this.put<ObjectiveProgressEntry>(`/progress-entries/${entryId}`, updates);
  }

  // ARCHIVES the entry. It is a leaf -- nothing goes with it.
  async deleteProgressEntry(entryId: number): Promise<ArchiveResponse> {
    return this.delete<ArchiveResponse>(`/progress-entries/${entryId}`);
  }

  // Bulk Operations
  async createGoalWithObjectives(goalData: CreateGoalRequest & { objectives: Omit<CreateObjectiveRequest, 'goal_id'>[] }): Promise<IEPGoal> {
    return this.post<IEPGoal>('/goals/with-objectives', goalData);
  }

  async duplicateGoal(goalId: number, targetStudentId?: number): Promise<IEPGoal> {
    return this.post<IEPGoal>(`/goals/${goalId}/duplicate`, { target_student_id: targetStudentId });
  }

  // Reporting and Analytics
  async getGoalProgress(goalId: number, dateFrom?: string, dateTo?: string): Promise<any> {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);

    const queryString = params.toString();
    return this.get(`/goals/${goalId}/progress-report${queryString ? `?${queryString}` : ''}`);
  }

  async getStudentGoalProgress(studentId: number, dateFrom?: string, dateTo?: string): Promise<any> {
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);

    const queryString = params.toString();
    return this.get(`/students/${studentId}/goal-progress${queryString ? `?${queryString}` : ''}`);
  }
}

export const goalsApi = new GoalsApiService();
export default goalsApi;
