/**
 * Ask the database to get up before anybody needs it.
 *
 * Without this, the honest state of the system arrives as a failure: a
 * therapist signs in, the dashboard fires five queries, and all five sit there
 * while the interceptor quietly waits out a 40-second resume. The overlay does
 * appear — but only *after* something has already gone wrong.
 *
 * So on mount, once the user is authenticated, ping `/api/health/ready` exactly
 * once. It is cheap (the backend probes with a short-timeout, unpooled engine
 * and never retries) and it answers one of three ways:
 *
 *   200                     → nothing to do, and nobody ever sees this code run
 *   503 code=DB_WAKING      → put the overlay up now and poll every 5s
 *   503 without a code      → something else is broken; say nothing, let the
 *                             real requests produce real errors
 *
 * The poll deliberately uses `dbWake: { skip: true }` so it does not enter the
 * retry interceptor: it is doing its own waiting, on its own schedule, and two
 * nested budgets would just make the give-up time unpredictable.
 */

import { useEffect } from 'react';

import { apiClient } from '../api/client';
import { apiLogger } from '../utils/logger';
import { DB_WAKING_CODE } from './policy';
import { dbWake } from './store';

/** Matches the backend's `Retry-After: 5`. */
const POLL_INTERVAL_MS = 5000;

/** Same budget the interceptor gives one request. Past this, stop pretending. */
const PREWARM_MAX_WAIT_MS = 120000;

const READY_PATH = '/api/health/ready';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type ReadyState = 'ready' | 'waking' | 'broken';

async function probeReady(): Promise<ReadyState> {
  try {
    const response = await apiClient.get<{ ready?: boolean; code?: string }>(READY_PATH, {
      dbWake: { skip: true },
      // A 503 is an answer, not an exception — we want to read its body.
      validateStatus: () => true,
      timeout: 15000,
    });

    if (response.status === 200) return 'ready';
    if (response.data?.code === DB_WAKING_CODE) return 'waking';
    return 'broken';
  } catch {
    // No answer at all. Could be a paused database behind a cold gateway, could
    // be the user's Wi-Fi. Treat it as "waking": the poll is bounded, and being
    // wrong here costs one honest overlay rather than a mystery hang later.
    return 'waking';
  }
}

/**
 * Poll readiness until the database answers, the budget runs out, or the caller
 * unmounts. Returns when it has stopped caring.
 */
async function waitForReady(isCancelled: () => boolean): Promise<void> {
  const startedAt = Date.now();
  let attempt = 0;

  while (!isCancelled() && Date.now() - startedAt < PREWARM_MAX_WAIT_MS) {
    attempt += 1;
    dbWake.noteAttempt(attempt);

    await sleep(POLL_INTERVAL_MS);
    if (isCancelled()) return;

    const state = await probeReady();
    if (state === 'ready') {
      apiLogger.info(
        `Database ready after ${Math.round((Date.now() - startedAt) / 1000)}s of pre-warming`
      );
      dbWake.clear();
      return;
    }
    if (state === 'broken') {
      apiLogger.warn('Readiness probe reports a failure that is not a wake-up; standing down');
      dbWake.clear();
      return;
    }
  }

  if (!isCancelled()) {
    apiLogger.error('Database did not come back within the pre-warm budget');
  }
  dbWake.clear();
}

/**
 * Ping readiness once after sign-in and hold the overlay up until the database
 * answers.
 *
 * @param enabled Pass the app's authenticated flag. While false this does
 *   nothing at all — the MSAL redirect dance must not be interrupted by an
 *   overlay, and an unauthenticated probe would be answered with a 401 anyway.
 */
export function useDbWakePrewarm(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    const isCancelled = () => cancelled;

    void (async () => {
      const state = await probeReady();
      if (cancelled || state !== 'waking') return;

      apiLogger.warn('Database is asleep; showing the wake-up overlay before anything fails');
      dbWake.begin();
      await waitForReady(isCancelled);
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled]);
}
