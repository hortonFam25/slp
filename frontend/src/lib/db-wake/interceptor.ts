/**
 * The axios response interceptor that waits out a database wake-up.
 *
 * The point of this file is that **callers never learn it happened**. A hook
 * that does `useQuery(['students'], listStudents)` sees a promise that took 40
 * seconds and then resolved, not a failure it has to know how to handle. The
 * only thing the rest of the app opts into is the overlay, which reads the
 * store this writes to.
 *
 * Ordering matters and is enforced in `client.ts`: this interceptor is
 * registered **before** the one that maps errors to `ApiError`, because it needs
 * the raw `AxiosError` (an `ApiError` has no `config` to re-send). Axios runs
 * response interceptors in registration order, so "registered first" means
 * "sees the error first"; anything this one rethrows falls through to the
 * `ApiError` mapping exactly as it did before.
 */

import type { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

import { apiLogger } from '../utils/logger';
import {
  DB_WAKE_EXHAUSTED,
  MAX_TOTAL_WAIT_MS,
  backoffMs,
  classifyFailure,
  retryDecision,
} from './policy';
import { dbWake } from './store';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const describe = (config: AxiosRequestConfig | undefined): string =>
  `${(config?.method ?? 'get').toUpperCase()} ${config?.url ?? '(unknown)'}`;

/** Mark an error as "already waited on", for the TanStack Query retry rule. */
function markExhausted<T>(error: T): T {
  try {
    (error as Record<string, unknown>)[DB_WAKE_EXHAUSTED] = true;
  } catch {
    // Frozen error object. The marker is an optimisation, not a correctness
    // requirement — the query layer just falls back to its default rule.
  }
  return error;
}

export function installDbWakeInterceptor(client: AxiosInstance): void {
  client.interceptors.response.use(
    (response) => {
      // Any genuinely successful answer means the database is up. Clear the
      // overlay even if the request that succeeded is not the one that raised
      // it — a poll, a parallel query, anything.
      //
      // The status check is not redundant: the readiness poller passes
      // `validateStatus: () => true` so it can read a 503 body, which lands
      // here rather than in the error handler. Clearing on that would dismiss
      // the overlay every five seconds, on the strength of a response that
      // says the database is still asleep.
      if (response.status < 400 && dbWake.isWaking()) dbWake.clear();
      return response;
    },
    async (error: AxiosError) => {
      const decision = retryDecision(error);
      const config = error.config;

      if (decision === 'none' || !config) {
        throw error;
      }

      if (decision === 'manual') {
        return waitForHuman(client, error, config);
      }

      return retryUntilAwake(client, error, config);
    }
  );
}

/**
 * Wait, re-send, repeat, until the database answers or the budget runs out.
 *
 * Resolving this promise resolves the caller's original promise, because an
 * axios rejection handler that *returns* a response puts the chain back on its
 * fulfilled path. That is the whole trick.
 */
async function retryUntilAwake(
  client: AxiosInstance,
  originalError: AxiosError,
  config: AxiosRequestConfig
): Promise<AxiosResponse> {
  dbWake.begin();
  apiLogger.warn(`Database appears to be waking up; holding ${describe(config)}`);

  let lastError: unknown = originalError;
  let waited = 0;

  for (let attempt = 1; ; attempt += 1) {
    const delay = backoffMs(attempt);
    if (waited + delay > MAX_TOTAL_WAIT_MS) break;

    dbWake.noteAttempt(attempt);
    await sleep(delay);
    waited += delay;

    try {
      // Back through the full client so the request interceptor re-attaches a
      // fresh MSAL token — two minutes is long enough for one to expire. The
      // `skip` flag stops this retry from entering the interceptor again and
      // starting a nested budget of its own.
      const response = await client({ ...config, dbWake: { skip: true } });
      apiLogger.info(
        `Database answered after ${attempt} attempt(s) (${Math.round(waited / 1000)}s); ` +
          `${describe(config)} resumed`
      );
      dbWake.clear();
      return response;
    } catch (retryError) {
      lastError = retryError;
      // Still asleep? Keep waiting. Anything else — a 401, a 500, a validation
      // error — is a real answer from a live server, so stop and report it.
      // `classifyFailure`, not `retryDecision`: our own re-send carries the
      // `skip` flag, which `retryDecision` would read as "leave it alone".
      if (classifyFailure(retryError as AxiosError) !== 'auto') {
        dbWake.clear();
        throw retryError;
      }
    }
  }

  apiLogger.error(
    `Database did not wake up within ${MAX_TOTAL_WAIT_MS / 1000}s; giving up on ${describe(config)}`
  );
  dbWake.clear();
  throw markExhausted(lastError);
}

/**
 * Park a write that failed with a raw network error and let a human decide.
 *
 * We genuinely do not know whether the server processed it — the request may
 * have landed and only the response been lost — so re-sending it is a decision
 * about the user's data, not about our retry policy. The promise returned here
 * stays pending until the overlay's button is pressed, which is intended: the
 * caller is waiting on a question that has been asked of somebody.
 */
function waitForHuman(
  client: AxiosInstance,
  originalError: AxiosError,
  config: AxiosRequestConfig
): Promise<AxiosResponse> {
  apiLogger.warn(
    `Lost connection during ${describe(config)}; not retrying a write automatically`
  );

  return new Promise<AxiosResponse>((resolve, reject) => {
    dbWake.requireManualRetry({
      label: describe(config),
      // Deliberately NOT skip-flagged: if this second attempt hits a DB_WAKING
      // 503, the normal auto-retry loop should take over from here.
      retry: () => resolve(client(config) as Promise<AxiosResponse>),
      dismiss: () => reject(markExhausted(originalError)),
    });
  });
}
