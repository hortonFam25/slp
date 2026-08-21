/**
 * The archive: the ledger of everything this app has hidden, and the one way
 * to put it back.
 *
 * Nothing in SLP Pro deletes clinical data any more. Every route that used to
 * DELETE now stamps rows with an archive event and hides them, and answers with
 * `{ archived: true, archiveEventId }` so the caller has the id it needs to
 * offer an undo. `POST /api/archive/events/{id}/restore` is that undo, and it
 * is exact: it clears the rows *this* event stamped and nothing else, so
 * restoring January's student archive never resurrects a goal retired in
 * September.
 *
 * See `backend/app/routers/archive.py` for the routes and
 * `backend/app/services/archive.py` for why the cascades are shaped the way
 * they are.
 */

import { BaseApiService } from './base';

/** The seven things that can be archived. Mirrors `ARCHIVABLE_ENTITY_TYPES`. */
export const ARCHIVABLE_ENTITY_TYPES = [
  'student',
  'goal',
  'objective',
  'progress_entry',
  'therapy_session',
  'appointment',
  'time_block',
] as const;

export type ArchivableEntityType = (typeof ARCHIVABLE_ENTITY_TYPES)[number];

/** What a therapist calls each of them. */
export const ENTITY_LABELS: Record<ArchivableEntityType, string> = {
  student: 'Student',
  goal: 'Goal',
  objective: 'Objective',
  progress_entry: 'Progress entry',
  therapy_session: 'Therapy session',
  appointment: 'Appointment',
  time_block: 'Time block',
};

/** The `contents` keys the backend emits, in the order worth reading them. */
export const CONTENT_LABELS: Record<string, string> = {
  students: 'students',
  goals: 'goals',
  objectives: 'objectives',
  progressEntries: 'progress entries',
  therapySessions: 'therapy sessions',
  appointments: 'appointments',
  timeBlocks: 'time blocks',
};

/**
 * What every former DELETE route now answers with.
 *
 * `message` is unchanged from the delete era on purpose — the app was written
 * against it. `archiveEventId` is the new part, and the reason an undo is
 * possible at all. It is optional in the type because a route may answer 204,
 * and because a caller that does not offer an undo must still typecheck.
 */
export interface ArchiveResponse {
  message?: string;
  archived?: boolean;
  archiveEventId?: number | null;
}

/** One archive event, with a count of the rows it still holds. */
export interface ArchiveEventSummary {
  eventId: number;
  userId: number;
  createdAt: string | null;
  rootEntityType: string;
  rootEntityId: number;
  reason: string | null;
  restored: boolean;
  restoredAt: string | null;
  restoredByUserId: number | null;
  /** `{ goals: 1, objectives: 3, progressEntries: 12 }` — empty once restored. */
  contents: Record<string, number>;
}

/** What a restore put back. */
export interface RestoreResult {
  eventId: number;
  rootEntityType: string;
  rootEntityId: number;
  restoredAt: string;
  restoredByUserId: number;
  restored: Record<string, number>;
  totalRows: number;
}

/** A row that is currently archived, named by identity rather than content. */
export interface ArchivedEntity {
  entityType: string;
  id: number;
  archivedAt: string | null;
  archiveEventId: number | null;
  /** Students only, and by ALIAS — the archive view never carries real names. */
  studentAlias: string | null;
}

export interface ArchiveEventsFilters {
  /** Default true on the server; pass false for "still archived" only. */
  include_restored?: boolean;
  root_entity_type?: ArchivableEntityType;
  limit?: number;
}

class ArchiveApiService extends BaseApiService {
  constructor() {
    super('/api/archive');
  }

  /** Archive events, newest first. Scoped to the caller by the server. */
  async listEvents(filters?: ArchiveEventsFilters): Promise<ArchiveEventSummary[]> {
    const params: Record<string, unknown> = {};
    if (filters?.include_restored !== undefined) {
      params.include_restored = filters.include_restored;
    }
    if (filters?.root_entity_type) {
      params.root_entity_type = filters.root_entity_type;
    }
    if (filters?.limit !== undefined) {
      params.limit = filters.limit;
    }
    return this.get<ArchiveEventSummary[]>('/events', params);
  }

  async getEvent(eventId: number): Promise<ArchiveEventSummary> {
    return this.get<ArchiveEventSummary>(`/events/${eventId}`);
  }

  /**
   * Reverse one archive event.
   *
   * 409 if it was already restored, or if the root's parent is still archived
   * (the message names the event to restore first).
   */
  async restoreEvent(eventId: number): Promise<RestoreResult> {
    return this.post<RestoreResult>(`/events/${eventId}/restore`, {});
  }

  /** Everything of one type that is currently archived. */
  async listArchived(
    entityType: ArchivableEntityType,
    limit?: number
  ): Promise<ArchivedEntity[]> {
    return this.get<ArchivedEntity[]>(
      `/archived/${entityType}`,
      limit === undefined ? undefined : { limit }
    );
  }
}

export const archiveApi = new ArchiveApiService();
export default archiveApi;
