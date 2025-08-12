// Goal Types and Interfaces

export interface GoalCategory {
  id: number;
  name: string;
  description?: string;
  is_active: boolean;
  created_date: string;
}

export interface ObjectiveProgressEntry {
  id: number;
  objective_id: number;
  progress_date: string;
  progress_on_objective?: string;
  progress_comments?: string;
  therapist_initials?: string;
  session_type?: string;
  student_id?: number;
  goal_id?: number;
  created_date: string;
  modified_date: string;
}

export interface GoalObjective {
  id: number;
  goal_id: number;
  objective_number: number;
  objective_description: string;
  progress_status?: string;
  schedule_frequency?: string;
  created_date: string;
  modified_date: string;
  progress_count: number;
  progress_entries?: ObjectiveProgressEntry[];
  latest_progress_entry?: ObjectiveProgressEntry;
}

export interface IEPGoal {
  id: number;
  student_id: number;
  goal_category_id: number;
  goal_number?: string;
  goal_description: string;
  target_behavior?: string;
  baseline_data?: string;
  target_criteria: string;
  goal_status: string;
  start_date: string;
  end_date?: string;
  mastery_date?: string;
  created_date: string;
  modified_date: string;
  objectives?: GoalObjective[];
  goal_category_name?: string;
}

export interface IEPGoalSummary {
  id: number;
  goal_number?: string;
  goal_description: string;
  goal_status: string;
  start_date: string;
  end_date?: string;
  mastery_date?: string;
  goal_category_name?: string;
  objectives_count: number;
}

export interface IEPGoalWithObjectives extends IEPGoal {
  objectives: GoalObjective[];
}

// Create/Update Types
export interface CreateGoalRequest {
  student_id: number;
  goal_category_id: number;
  goal_number?: string;
  goal_description: string;
  target_behavior?: string;
  baseline_data?: string;
  target_criteria: string;
  goal_status?: string;
  start_date: string;
  end_date?: string;
  mastery_date?: string;
}

export interface UpdateGoalRequest {
  goal_category_id?: number;
  goal_number?: string;
  goal_description?: string;
  target_behavior?: string;
  baseline_data?: string;
  target_criteria?: string;
  goal_status?: string;
  start_date?: string;
  end_date?: string;
  mastery_date?: string;
}

export interface CreateObjectiveRequest {
  goal_id: number;
  objective_number: number;
  objective_description: string;
  progress_status?: string;
  schedule_frequency?: string;
}

export interface UpdateObjectiveRequest {
  objective_description?: string;
  progress_status?: string;
  schedule_frequency?: string;
}

export interface CreateProgressEntryRequest {
  objective_id: number;
  progress_date: string;
  progress_on_objective?: string;
  progress_comments?: string;
  therapist_initials?: string;
  session_type?: string;
}

export interface UpdateProgressEntryRequest {
  progress_date?: string;
  progress_on_objective?: string;
  progress_comments?: string;
  therapist_initials?: string;
  session_type?: string;
}

// Filter and Query Types
export interface GoalsFilters {
  student_id?: number;
  goal_status?: string;
  goal_category_id?: number;
  start_date_from?: string;
  start_date_to?: string;
}

export interface ObjectivesFilters {
  goal_id?: number;
  progress_status?: string;
  schedule_frequency?: string;
}

export interface ProgressEntriesFilters {
  objective_id?: number;
  progress_date_from?: string;
  progress_date_to?: string;
  therapist_initials?: string;
}

// CSV Import Types for Goals
export interface GoalCSVRow {
  goal: string;
  goal_type: string;
  goal_number?: string;
  objective1?: string;
  progress1?: string;
  schedule1?: string;
  prog_date1?: string;
  prog_obj1?: string;
  prog_comments1?: string;
  prog_initials1?: string;
  objective2?: string;
  progress2?: string;
  schedule2?: string;
  prog_date2?: string;
  prog_obj2?: string;
  prog_comments2?: string;
  prog_initials2?: string;
  objective3?: string;
  progress3?: string;
  schedule3?: string;
  prog_date3?: string;
  prog_obj3?: string;
  prog_comments3?: string;
  prog_initials3?: string;
  objective4?: string;
  progress4?: string;
  schedule4?: string;
  prog_date4?: string;
  prog_obj4?: string;
  prog_comments4?: string;
  prog_initials4?: string;
}

// Goal Status Constants
export const GOAL_STATUS_OPTIONS = [
  'Active',
  'Mastered',
  'Discontinued',
  'Modified',
  'On Hold'
] as const;

export type GoalStatus = typeof GOAL_STATUS_OPTIONS[number];

// Schedule Frequency Constants
export const SCHEDULE_FREQUENCY_OPTIONS = [
  'Daily',
  'Weekly',
  'Bi-weekly',
  'Monthly',
  'Quarterly',
  'As Needed'
] as const;

export type ScheduleFrequency = typeof SCHEDULE_FREQUENCY_OPTIONS[number];

// Session Type Constants
export const SESSION_TYPE_OPTIONS = [
  'Individual',
  'Group',
  'Consultation',
  'Assessment',
  'Other'
] as const;

export type SessionType = typeof SESSION_TYPE_OPTIONS[number];
