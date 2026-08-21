/**
 * The one pending "Undo" the app is currently offering.
 *
 * Modelled on `lib/db-wake/store.ts` and for the same reason: the writer is a
 * hook that fires from a dozen unrelated screens, and the reader is a single
 * snackbar mounted once in `App.tsx`. A React context would force every one of
 * those screens to render its own snackbar, and "identical everywhere" is the
 * entire point of this module.
 *
 * Only ONE undo is held at a time. Archiving a second thing replaces the offer
 * rather than queueing it: two stacked snackbars both reading "Undo" is a
 * coin-flip about which row comes back, and the archive page is the honest way
 * to reverse something you have moved past.
 */

import { create } from 'zustand';

export interface PendingUndo {
  /** Monotonic; keys the snackbar so a second archive re-animates it. */
  key: number;
  /** "Goal archived." — what the snackbar says happened. */
  message: string;
  /** Put it back. Rejecting surfaces as an error in the snackbar. */
  undo: () => Promise<void>;
}

export interface ArchiveUndoState {
  pending: PendingUndo | null;
  /** True while `undo()` is in flight; the button shows a spinner and locks. */
  undoing: boolean;
  /** Set when an undo failed, so the user is told rather than left guessing. */
  error: string | null;

  /** Offer an undo, replacing any offer already on screen. */
  offer: (entry: Omit<PendingUndo, 'key'>) => void;
  /** Run the pending undo. No-op if there is none or one is already running. */
  runUndo: () => Promise<void>;
  /** The snackbar timed out or was dismissed. The archive stands. */
  dismiss: () => void;
  clearError: () => void;
}

let nextKey = 1;

export const useArchiveUndoStore = create<ArchiveUndoState>((set, get) => ({
  pending: null,
  undoing: false,
  error: null,

  offer: (entry) => {
    set({ pending: { ...entry, key: nextKey++ }, undoing: false, error: null });
  },

  runUndo: async () => {
    const { pending, undoing } = get();
    if (!pending || undoing) return;
    set({ undoing: true, error: null });
    try {
      await pending.undo();
      set({ pending: null, undoing: false });
    } catch (error) {
      // Keep the offer up. A restore can fail for a reason the user can act on
      // -- most often "the parent is still archived, restore that first" -- and
      // dropping the snackbar would take the message with it.
      set({
        undoing: false,
        error: error instanceof Error ? error.message : 'Could not undo that.',
      });
    }
  },

  dismiss: () => set({ pending: null, undoing: false, error: null }),

  clearError: () => set({ error: null }),
}));

/** Non-React write, for callers that are not components. */
export const archiveUndo = {
  offer: (entry: Omit<PendingUndo, 'key'>) => useArchiveUndoStore.getState().offer(entry),
  dismiss: () => useArchiveUndoStore.getState().dismiss(),
};
