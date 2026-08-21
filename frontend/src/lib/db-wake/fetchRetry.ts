/**
 * The same wake-up handling as `interceptor.ts`, for the one request that
 * cannot go through axios.
 *
 * `aiChatApi.sendMessageStream` reads a Server-Sent Events body incrementally.
 * Axios in the browser buffers the whole response before resolving, so that
 * call has to be raw `fetch` — and raw `fetch` never touches the axios
 * interceptor, which meant a paused database turned the chat into a bare
 * "Streaming request failed (503)" while every other screen waited politely.
 *
 * This closes that hole without moving the streaming call onto axios. The
 * policy is shared, not re-decided: `isDbWakingBody`, `backoffMs` and
 * `MAX_TOTAL_WAIT_MS` all come from `policy.ts`, and the overlay is the same
 * one, driven by the same store.
 *
 * ## Why `send` is a factory and not a Request
 *
 * A wake-up can take a minute, which is long enough for an MSAL token to
 * expire. The interceptor re-enters the full axios client so its request
 * interceptor re-attaches a fresh one; the equivalent here is asking the caller
 * to rebuild the request each attempt. Passing a `Request` object would also be
 * wrong for a second reason: a `Request` with a body can only be sent once.
 */

import { apiLogger } from '../utils/logger';
import { DB_WAKE_EXHAUSTED, DB_WAKING_CODE, MAX_TOTAL_WAIT_MS, backoffMs } from './policy';
import { dbWake } from './store';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * A 503 our own handler produced.
 *
 * Reads a CLONE, never the response itself: a body can only be consumed once,
 * and the response that turns out not to be a wake-up is handed straight back
 * to the caller with its stream still unread — which for the chat route is the
 * entire point.
 */
async function isDbWakingBody(response: Response): Promise<boolean> {
  if (response.status !== 503) return false;
  try {
    const data = (await response.clone().json()) as { code?: string } | null;
    return data?.code === DB_WAKING_CODE;
  } catch {
    // A 503 from something in front of the app (a proxy, App Service itself)
    // has no JSON body. Not ours; let the caller deal with it.
    return false;
  }
}

/** Mark an error the retry loop already spent its budget on. */
function markExhausted<T>(error: T): T {
  try {
    (error as Record<string, unknown>)[DB_WAKE_EXHAUSTED] = true;
  } catch {
    // Frozen error. The marker is an optimisation, not a correctness need.
  }
  return error;
}

export interface FetchThroughDbWakeOptions {
  /** Method + path, for the log line and the overlay's parked-request label. */
  label: string;
  /**
   * True only for a request that is safe to send twice. A raw network error on
   * a write is NOT retried automatically — the request may have landed and only
   * the response been lost — so it is parked for a human exactly as the axios
   * interceptor parks one. Defaults to false, the careful answer.
   */
  idempotent?: boolean;
}

/**
 * Send, and keep sending while the database is waking up.
 *
 * `send` must build the whole request from scratch each call, headers included.
 * Resolves with the first response that is not a `DB_WAKING` 503; throws if the
 * budget runs out, or if the caller declines to re-send a lost write.
 */
export async function fetchThroughDbWake(
  send: () => Promise<Response>,
  { label, idempotent = false }: FetchThroughDbWakeOptions
): Promise<Response> {
  let first: Response;
  try {
    first = await send();
  } catch (networkError) {
    // No response at all. Identical reasoning to `policy.classifyFailure`:
    // a GET can be re-sent on our own authority, a write cannot.
    if (idempotent) return retryUntilAwake(send, label, networkError);
    return waitForHuman(send, label, networkError);
  }

  if (!(await isDbWakingBody(first))) return first;

  return retryUntilAwake(send, label, new Error(`${label} — database is waking up`));
}

async function retryUntilAwake(
  send: () => Promise<Response>,
  label: string,
  originalError: unknown
): Promise<Response> {
  dbWake.begin();
  apiLogger.warn(`Database appears to be waking up; holding ${label}`);

  let lastError: unknown = originalError;
  let waited = 0;

  for (let attempt = 1; ; attempt += 1) {
    const delay = backoffMs(attempt);
    if (waited + delay > MAX_TOTAL_WAIT_MS) break;

    dbWake.noteAttempt(attempt);
    await sleep(delay);
    waited += delay;

    try {
      const response = await send();
      if (await isDbWakingBody(response)) {
        lastError = new Error(`${label} — database still waking up`);
        continue;
      }
      apiLogger.info(
        `Database answered after ${attempt} attempt(s) (${Math.round(waited / 1000)}s); ${label} resumed`
      );
      dbWake.clear();
      return response;
    } catch (retryError) {
      // Still no connection at all. Keep waiting: we only reached this loop
      // because the failure was already classified as wake-up-shaped.
      lastError = retryError;
    }
  }

  apiLogger.error(
    `Database did not wake up within ${MAX_TOTAL_WAIT_MS / 1000}s; giving up on ${label}`
  );
  dbWake.clear();
  throw markExhausted(
    lastError instanceof Error ? lastError : new Error(`${label} failed while the database was asleep`)
  );
}

/**
 * Park a lost write and let the overlay ask. The returned promise stays pending
 * until a button is pressed, which is the point: the caller is waiting on a
 * question that has been put to somebody.
 */
function waitForHuman(
  send: () => Promise<Response>,
  label: string,
  originalError: unknown
): Promise<Response> {
  apiLogger.warn(`Lost connection during ${label}; not retrying a write automatically`);

  return new Promise<Response>((resolve, reject) => {
    dbWake.requireManualRetry({
      label,
      retry: () => resolve(send()),
      dismiss: () =>
        reject(
          markExhausted(
            originalError instanceof Error ? originalError : new Error(`${label} failed`)
          )
        ),
    });
  });
}
