/**
 * One way to archive something, used by every screen that can.
 *
 * The shape of the problem: a dozen call sites each had their own delete
 * handler, their own confirmation copy and their own idea of what to refresh
 * afterwards. Archiving added a fourth thing to get right — the undo — and
 * "each site does it slightly differently" is not an option for a button whose
 * job is to reassure.
 *
 * So every site now does:
 *
 * ```tsx
 * const archiveWithUndo = useArchiveWithUndo();
 * ...
 * await archiveWithUndo({
 *   entity: 'goal',
 *   name: `Goal ${goal.goal_number}`,
 *   archive: () => goalsApi.deleteGoal(goal.id),   // still DELETE; it archives
 *   invalidateKeys: [['goals']],
 *   onChanged: () => refreshGoals(),
 * });
 * ```
 *
 * and gets the same snackbar, the same undo, and the same refresh on both the
 * archive and the undo.
 *
 * ## Why the caller still passes the request
 *
 * Because the routes are not uniform: a goal archives through
 * `DELETE /api/goals/{id}`, a student through `DELETE /api/students/{id}` *or*
 * `PUT /api/students/{id}/archive` depending on which button was pressed. What
 * IS uniform is the answer — `{ archived, archiveEventId }` — and that is what
 * this hook consumes.
 *
 * ## Why `undo` is overridable
 *
 * The default undo is `POST /api/archive/events/{id}/restore`, which is exact
 * and works for every route that returns an `archiveEventId`. The student
 * Archive button predates the framework and answers with a `StudentRead` that
 * carries no event id; it passes its own undo (`PUT .../unarchive`), which
 * restores the same event server-side. Both paths end up reversing the same
 * thing.
 */

import { useCallback } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';

import { archiveApi, type ArchivableEntityType, type ArchiveResponse } from '../api/archive';
import { archivedToast } from './copy';
import { useArchiveUndoStore } from './store';

export interface ArchiveWithUndoOptions<T extends ArchiveResponse | void | unknown> {
  /** Which of the seven things this is. Drives the snackbar wording. */
  entity: ArchivableEntityType;
  /** What identifies it to the person who pressed the button, if anything. */
  name?: string;
  /** The request. Whatever it resolves to is handed back to `undo`. */
  archive: () => Promise<T>;
  /**
   * Put it back. Defaults to restoring the `archiveEventId` in the response.
   * Return without throwing to mean "restored"; throw to show the reason.
   */
  undo?: (result: T) => Promise<unknown>;
  /** Query keys to invalidate after the archive AND after a successful undo. */
  invalidateKeys?: QueryKey[];
  /**
   * Same moments, for the screens still on plain `useState` data hooks.
   *
   * Returns `unknown` rather than `void | Promise<void>` so a one-line
   * `() => refetch()` typechecks whatever the caller's refetch resolves to --
   * a TanStack `refetch()` hands back a `QueryObserverResult`, and forcing
   * every call site to wrap that in braces buys nothing.
   */
  onChanged?: () => unknown;
  /**
   * Set false for a screen that cannot show an undo honestly — e.g. one whose
   * data is gone from the client the moment the row disappears. The archive
   * still happens; only the snackbar is skipped.
   */
  offerUndo?: boolean;
}

/** The `archiveEventId` in an archive response, if there is one. */
function eventIdOf(result: unknown): number | null {
  if (!result || typeof result !== 'object') return null;
  const id = (result as ArchiveResponse).archiveEventId;
  return typeof id === 'number' ? id : null;
}

export function useArchiveWithUndo() {
  const queryClient = useQueryClient();
  const offer = useArchiveUndoStore((s) => s.offer);

  return useCallback(
    async <T extends ArchiveResponse | void | unknown>(
      options: ArchiveWithUndoOptions<T>
    ): Promise<T> => {
      const {
        entity,
        name,
        archive,
        undo,
        invalidateKeys = [],
        onChanged,
        offerUndo = true,
      } = options;

      // Deliberately NOT caught. Every call site already had error handling for
      // its delete, and swallowing the rejection here would turn a failed
      // archive into a silent no-op with a cheerful snackbar over it.
      const result = await archive();

      const refresh = async () => {
        invalidateKeys.forEach((key) => {
          void queryClient.invalidateQueries({ queryKey: key });
        });
        await onChanged?.();
      };

      await refresh();

      if (!offerUndo) return result;

      const eventId = eventIdOf(result);
      const undoFn = undo
        ? () => undo(result)
        : eventId !== null
          ? () => archiveApi.restoreEvent(eventId)
          : null;

      // No event id and no custom undo means the route did not tell us how to
      // reverse it. Say nothing rather than offer a button that cannot work —
      // the Archive page can still restore it.
      if (!undoFn) return result;

      offer({
        message: archivedToast(entity, name),
        undo: async () => {
          await undoFn();
          await refresh();
        },
      });

      return result;
    },
    [offer, queryClient]
  );
}
