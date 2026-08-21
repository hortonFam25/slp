/**
 * The rules of waiting out an Azure SQL Serverless wake-up.
 *
 * Production runs on a serverless tier that auto-pauses after 60 idle minutes.
 * The first request after a pause spends 30-60 seconds waiting for compute to
 * come back. This module holds every decision about that wait — which failures
 * count, how long to wait between tries, when to stop — so the interceptor
 * reads as a loop and the policy can be argued with in one place.
 *
 * Nothing here touches React, axios instances, or the store. It is pure
 * predicates and arithmetic.
 */

import type { AxiosError, AxiosRequestConfig } from 'axios';

/**
 * The wire contract with the backend. Mirrors
 * `backend/app/db/pause_signatures.py`. The backend answers a paused database
 * with `503 {"detail": "Database is waking up", "code": "DB_WAKING"}` and a
 * `Retry-After: 5` header; we key off `code` and nothing else, because `detail`
 * is prose and prose gets reworded.
 */
export const DB_WAKING_CODE = 'DB_WAKING';

/**
 * Backoff schedule, in milliseconds, indexed by attempt number (1-based).
 * 2s, 4s, 8s, then 10s forever — front-loaded because a database that was only
 * briefly asleep answers almost immediately, flat afterwards because a real
 * resume takes 30-60 seconds and doubling past 10s just adds dead air.
 */
const BACKOFF_MS = [2000, 4000, 8000];
const STEADY_BACKOFF_MS = 10000;

/**
 * Total time we are willing to spend waiting, across all attempts, for one
 * request. Roughly double the worst resume Azure documents: long enough that a
 * genuine wake-up always finishes inside it, short enough that a database which
 * is actually down produces an error rather than a spinner that never ends.
 */
export const MAX_TOTAL_WAIT_MS = 120000;

/** The delay before attempt `n` (1-based). */
export function backoffMs(attempt: number): number {
  return BACKOFF_MS[attempt - 1] ?? STEADY_BACKOFF_MS;
}

/**
 * Stamped on an error the interceptor already spent its full budget on, so the
 * TanStack Query layer can tell "nobody has tried yet" from "we just spent two
 * minutes on this" and decline to start a second retry storm behind the first.
 * See `queryRetry.ts`.
 */
export const DB_WAKE_EXHAUSTED = '__dbWakeExhausted';

/** Per-request bookkeeping, hung off the axios config. */
export interface DbWakeMeta {
  /** Set on requests the interceptor must ignore: its own retries, and the
   *  readiness poll (which does its own waiting and would otherwise recurse). */
  skip?: boolean;
}

declare module 'axios' {
  // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
  export interface AxiosRequestConfig {
    dbWake?: DbWakeMeta;
  }
}

/** A 503 that our own handler produced. */
export function isDbWakingResponse(error: AxiosError): boolean {
  const response = error.response;
  if (!response || response.status !== 503) return false;
  const data = response.data as { code?: string } | undefined;
  return data?.code === DB_WAKING_CODE;
}

/**
 * No response at all: DNS failure, connection refused, TLS reset, or our own
 * 120-second axios timeout. This is what a paused database looked like before
 * the backend handler existed, and it is still what a cold App Service worker
 * or a dropped Wi-Fi connection looks like — which is why it is treated far
 * more carefully than a DB_WAKING 503 (see `retryDecision`).
 */
export function isNetworkError(error: AxiosError): boolean {
  if (error.response) return false;
  return (
    error.code === 'ERR_NETWORK' ||
    error.code === 'ECONNABORTED' ||
    error.code === 'ETIMEDOUT' ||
    error.message === 'Network Error' ||
    /timeout/i.test(error.message ?? '')
  );
}

/** GET/HEAD/OPTIONS — safe to send twice by definition. */
export function isIdempotent(config: AxiosRequestConfig | undefined): boolean {
  const method = (config?.method ?? 'get').toLowerCase();
  return method === 'get' || method === 'head' || method === 'options';
}

export type RetryDecision =
  /** Wait and re-send it ourselves; the caller never learns it happened. */
  | 'auto'
  /** Show the overlay and let a human decide, because re-sending might duplicate a write. */
  | 'manual'
  /** Not our problem. Reject and let normal error handling run. */
  | 'none';

/**
 * The whole idempotency argument, in one function.
 *
 * A **DB_WAKING 503** is safe to retry for *any* method, including POST and
 * DELETE. The backend raises it while acquiring the connection — the statement
 * never reached the server, so there is nothing half-written behind it. That
 * promise is asserted by a backend test
 * (`test_pause_on_a_write_is_also_503_db_waking`) precisely because this
 * decision depends on it.
 *
 * A **raw network error** carries no such promise. The request may have been
 * fully processed and only the *response* lost — a POST retried on that basis
 * can create the same therapy session twice. So:
 *
 *   - GET/HEAD/OPTIONS → retry automatically. Worst case we read twice.
 *   - POST/PUT/PATCH/DELETE → never automatically. Put the overlay up with a
 *     "Try again" button and let the therapist, who knows what they just did,
 *     make the call.
 */
export function classifyFailure(error: AxiosError): RetryDecision {
  if (isDbWakingResponse(error)) return 'auto';

  if (isNetworkError(error)) {
    return isIdempotent(error.config) ? 'auto' : 'manual';
  }

  return 'none';
}

/**
 * `classifyFailure`, plus the guard that keeps the interceptor from re-entering
 * itself. The retry loop calls `classifyFailure` directly, because its own
 * re-sends carry `skip` and would otherwise classify as "not our problem".
 */
export function retryDecision(error: AxiosError): RetryDecision {
  if (error.config?.dbWake?.skip) return 'none';
  return classifyFailure(error);
}
