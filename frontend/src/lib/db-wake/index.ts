/**
 * Graceful handling for Azure SQL Serverless waking up from auto-pause.
 *
 * Four pieces, wired in three places:
 *
 *   policy.ts        what counts as a wake-up, and how long to wait
 *   store.ts         whether the app currently believes the DB is asleep
 *   interceptor.ts   installed in lib/api/client.ts — absorbs the failures
 *   fetchRetry.ts    used in lib/api/aiChat.ts — the same, for the one
 *                    streaming request that cannot go through axios
 *   prewarm.ts       used in App.tsx — asks before anybody needs an answer
 *   queryRetry.ts    used in main.tsx — keeps TanStack Query out of the way
 *
 * The contract with the backend is one string: a 503 whose body carries
 * `{"code": "DB_WAKING"}`. See docs/DATABASE.md.
 */

export { DatabaseWakingOverlay } from './DatabaseWakingOverlay';
export { installDbWakeInterceptor } from './interceptor';
export {
  DB_WAKING_CODE,
  MAX_TOTAL_WAIT_MS,
  backoffMs,
  classifyFailure,
  isDbWakingResponse,
  isIdempotent,
  isNetworkError,
  retryDecision,
} from './policy';
export type { RetryDecision } from './policy';
export { fetchThroughDbWake } from './fetchRetry';
export type { FetchThroughDbWakeOptions } from './fetchRetry';
export { useDbWakePrewarm } from './prewarm';
export { QUERY_MAX_RETRIES, dbWakeAwareRetry, dbWakeAwareRetryDelay } from './queryRetry';
export { dbWake, useDbWakeStore } from './store';
export type { DbWakeState, ManualRetry } from './store';
