/**
 * What the app knows about the database being asleep.
 *
 * One tiny zustand store, written to by the axios interceptor and the pre-warm
 * poller, read by `<DatabaseWakingOverlay/>`. Deliberately not a React context:
 * the writers are not components, and an interceptor should not have to be
 * mounted inside a provider to report what it just saw.
 */

import { create } from 'zustand';

/**
 * A request that failed in a way we refuse to retry on our own — a raw network
 * error on a write, where re-sending could duplicate it. Held until a human
 * chooses. Both callbacks settle the caller's original promise, so nothing
 * upstream is left hanging once one of them fires.
 */
export interface ManualRetry {
  /** Method + path, for nothing but the console log. */
  label: string;
  /** Re-send the request and resolve the original promise with the result. */
  retry: () => void;
  /** Give up and reject the original promise with the original error. */
  dismiss: () => void;
}

export interface DbWakeState {
  /** True while we believe the database is resuming. Drives the overlay. */
  waking: boolean;
  /** Which retry we are on, 1-based. 0 while not retrying. */
  attempt: number;
  /** When this wake-up episode started, for the "Xs elapsed" counter. */
  startedAt: number | null;
  /** Non-empty when the overlay must offer a button instead of a spinner. */
  manualRetries: ManualRetry[];

  /** Begin (or continue) a wake-up episode. Idempotent. */
  beginWaking: () => void;
  /** Record that we are about to make attempt `attempt`. */
  noteAttempt: (attempt: number) => void;
  /** The database answered, or we gave up. Either way, stop showing the overlay. */
  clearWaking: () => void;

  /** Park a request until a human presses a button. */
  requireManualRetry: (entry: ManualRetry) => void;
  /** "Try again" — re-send everything parked. */
  retryAllManual: () => void;
  /** "Dismiss" — reject everything parked with its original error. */
  dismissAllManual: () => void;
}

export const useDbWakeStore = create<DbWakeState>((set, get) => ({
  waking: false,
  attempt: 0,
  startedAt: null,
  manualRetries: [],

  beginWaking: () => {
    // Concurrent requests all discover the pause at once; the first one to get
    // here owns `startedAt` so the elapsed counter measures the episode rather
    // than resetting on every straggler.
    if (get().waking) return;
    set({ waking: true, attempt: 0, startedAt: Date.now() });
  },

  noteAttempt: (attempt) => {
    // Several requests may be retrying in parallel. Show the furthest along —
    // a counter that jumps backwards reads as a bug to the person watching it.
    set((state) => ({ attempt: Math.max(state.attempt, attempt) }));
  },

  clearWaking: () => {
    // A parked manual retry outlives the auto-retry loop that gave up: the
    // overlay has to stay put until the human answers it.
    if (get().manualRetries.length > 0) return;
    set({ waking: false, attempt: 0, startedAt: null });
  },

  requireManualRetry: (entry) => {
    set((state) => ({
      waking: true,
      startedAt: state.startedAt ?? Date.now(),
      manualRetries: [...state.manualRetries, entry],
    }));
  },

  retryAllManual: () => {
    const parked = get().manualRetries;
    // Clear first: each `retry()` re-enters the interceptor, which may park a
    // fresh entry, and that entry must not be wiped by this call's own cleanup.
    set({ manualRetries: [], waking: false, attempt: 0, startedAt: null });
    parked.forEach((entry) => entry.retry());
  },

  dismissAllManual: () => {
    const parked = get().manualRetries;
    set({ manualRetries: [], waking: false, attempt: 0, startedAt: null });
    parked.forEach((entry) => entry.dismiss());
  },
}));

/** Non-React read/write, for the interceptor and the pre-warm poller. */
export const dbWake = {
  begin: () => useDbWakeStore.getState().beginWaking(),
  noteAttempt: (attempt: number) => useDbWakeStore.getState().noteAttempt(attempt),
  clear: () => useDbWakeStore.getState().clearWaking(),
  requireManualRetry: (entry: ManualRetry) =>
    useDbWakeStore.getState().requireManualRetry(entry),
  isWaking: () => useDbWakeStore.getState().waking,
};
