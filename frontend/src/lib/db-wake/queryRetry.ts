/**
 * TanStack Query defaults that cooperate with the axios interceptor.
 *
 * ## The interplay, because it is easy to get wrong
 *
 * There are two retry layers in this app and they are *not* peers:
 *
 * ```
 *   useQuery  ──▶  queryFn  ──▶  apiClient  ──▶  [ db-wake interceptor ]  ──▶  server
 *      ▲                                                 │
 *      └───────────── only sees what the interceptor gives up on ─────────┘
 * ```
 *
 * The interceptor owns wake-up retries entirely. It absorbs a `DB_WAKING` 503
 * (any method) and a network error on a GET, and re-sends for up to two
 * minutes. Query never sees those failures at all — the promise it is awaiting
 * simply takes longer and then resolves.
 *
 * So by the time an error *does* reach the Query layer, one of three things is
 * true:
 *
 * 1. the interceptor spent its whole 120-second budget and gave up — retrying
 *    here would start a second two-minute storm behind the first, and with
 *    `retry: 2` on N mounted queries that is 3N requests at a database that has
 *    already been asked politely for two minutes;
 * 2. the interceptor declined on purpose (a write that lost its connection) and
 *    a human is being asked about it in the overlay — a background retry would
 *    answer that question for them, in the direction of "send it again";
 * 3. it is an ordinary error and has nothing to do with the database.
 *
 * Only case 3 is Query's to retry. Case 1 and 2 are both marked with
 * `DB_WAKE_EXHAUSTED` by the interceptor, which is what `dbWakeAwareRetry`
 * checks first. Everything else keeps a short, conventional policy: never retry
 * a 4xx (the request is wrong; sending it again will not fix it), retry
 * anything else twice with backoff.
 *
 * The previous default was a flat `retry: 1`, which retried 404s and gave a
 * transient 502 exactly one immediate second chance.
 */

import { DB_WAKE_EXHAUSTED } from './policy';

/** True if the db-wake interceptor already handled (and gave up on) this error. */
function wasHandledByDbWake(error: unknown): boolean {
  return Boolean(
    error && typeof error === 'object' && (error as Record<string, unknown>)[DB_WAKE_EXHAUSTED]
  );
}

/** `ApiError` and `AxiosError` both expose a status; read it without importing either. */
function statusOf(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const candidate = error as { status?: unknown; response?: { status?: unknown } };
  const status = candidate.status ?? candidate.response?.status;
  return typeof status === 'number' ? status : undefined;
}

export const QUERY_MAX_RETRIES = 2;

export function dbWakeAwareRetry(failureCount: number, error: unknown): boolean {
  if (wasHandledByDbWake(error)) return false;

  const status = statusOf(error);
  if (status !== undefined && status >= 400 && status < 500) return false;

  return failureCount < QUERY_MAX_RETRIES;
}

/** 1s, 2s. Short on purpose — the long waits belong to the interceptor. */
export function dbWakeAwareRetryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 8000);
}
