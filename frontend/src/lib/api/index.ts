// Central API exports - Single source of truth for all API interactions

// Core infrastructure
export { apiClient, makeApiRequest } from './client';
export { BaseApiService } from './base';
export { ApiError, handleApiError, ERROR_MESSAGES } from './errors';
export { API_ENDPOINTS } from './types';
export type { ApiResponse, ApiError as ApiErrorType, PaginatedResponse, BaseQueryParams } from './types';

// Domain-specific APIs
export { studentsApi } from './students';
export type { 
  Student, 
  StudentSummary, 
  CreateStudentRequest, 
  UpdateStudentRequest, 
  StudentsFilters 
} from './students';

export { csvApi } from './csv';
export type {
  CSVImportResult,
  CSVPreviewResult,
  CSVImportOptions
} from './csv';

export { goalsApi } from './goals';
export type {
  IEPGoal,
  IEPGoalSummary,
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
  GOAL_STATUS_OPTIONS,
  SCHEDULE_FREQUENCY_OPTIONS,
  SESSION_TYPE_OPTIONS
} from './types/goals';

export { schoolsApi } from './schools';
export type {
  School,
  SchoolSummary,
  CreateSchoolRequest,
  UpdateSchoolRequest,
  SchoolsFilters,
  SchoolStatistics,
  TeacherSchoolAssignment,
  CreateTeacherSchoolAssignmentRequest
} from './types/schools';

export { teachersApi } from './teachers';
export type {
  Teacher,
  TeacherSummary,
  CreateTeacherRequest,
  UpdateTeacherRequest,
  TeachersFilters,
  TeacherStatistics,
  StudentTeacherAssignment,
  CreateStudentTeacherAssignmentRequest,
  CONTACT_METHODS,
  ContactMethod
} from './types/teachers';

export { schedulingApi } from './scheduling';
export type {
  Appointment,
  AppointmentSummary,
  AppointmentWithDetails,
  AppointmentCreate,
  AppointmentUpdate,
  TimeBlock,
  TimeBlockSummary,
  TimeBlockWithStudents,
  TimeBlockCreate,
  TimeBlockUpdate,
  AppointmentFilters,
  TimeBlockFilters
} from './scheduling';
// Note: StudentSummary is also exported from './students' - using scheduling version for time blocks

export { therapySessionsApi } from './therapySessions';
export type { 
  TherapySession, 
  TherapySessionSummary, 
  CreateTherapySessionRequest, 
  UpdateTherapySessionRequest,
  StartSessionRequest, 
  CompleteSessionRequest,
  SessionGoal,
  SessionObjective,
  TherapySessionFilters,
  SessionStatistics
} from './therapySessions';

export { archiveApi, ARCHIVABLE_ENTITY_TYPES, ENTITY_LABELS, CONTENT_LABELS } from './archive';
export type {
  ArchivableEntityType,
  ArchiveResponse,
  ArchiveEventSummary,
  ArchiveEventsFilters,
  ArchivedEntity,
  RestoreResult
} from './archive';

export { apiTokensApi, MAX_MANUAL_TOKENS, isTokenLimitError, tokenLimitMessage } from './apiTokens';
export type { ApiToken, ApiTokenCreated, ApiTokenKind } from './apiTokens';

// Future API services will be exported here:
// export { assessmentsApi } from './assessments';
// export { progressApi } from './progress';
// export { servicesApi } from './services';
// export { eligibilitiesApi } from './eligibilities';

// Consolidated API object for easy access
export const api = {
  students: studentsApi,
  csv: csvApi,
  goals: goalsApi,
  schools: schoolsApi,
  teachers: teachersApi,
  scheduling: schedulingApi,
  therapySessions: therapySessionsApi,
  // NOT extended with `archive` / `apiTokens`. Every entry in this object is
  // already a `TS2304: Cannot find name` -- `export { x } from` re-exports
  // without binding `x` locally -- and adding a line here would add another
  // pre-existing-shaped error rather than a usable member. Import
  // `archiveApi` / `apiTokensApi` from their modules (or the named re-exports
  // above) instead.
  // assessments: assessmentsApi,
  // progress: progressApi,
  // services: servicesApi,
  // eligibilities: eligibilitiesApi,
};

export default api;
