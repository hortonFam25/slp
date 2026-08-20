/**
 * Surviving the sign-in redirect with a connector request.
 *
 * MSAL's redirectUri is the bare origin, so a therapist who lands on
 * /connect/authorize?client_id=... while signed out comes back from Entra at
 * "/" with the whole OAuth query string gone - and an authorization request
 * cannot be reconstructed, so the connector would simply fail with nothing to
 * explain it. Stash it before MSAL runs, replay it once we are back.
 *
 * sessionStorage, matching where the request belongs: the tab that started it,
 * and it dies with that tab.
 */
const KEY = 'slppro-pending-connect';

export const CONSENT_PATH = '/connect/authorize';

function store(): Storage | null {
  try {
    return window.sessionStorage ?? null;
  } catch {
    return null;
  }
}

/**
 * A stored value is replayed straight into the router, so it is only ever a
 * QUERY STRING - never a path - and it must carry the one parameter that makes
 * the request an authorization request at all.
 */
function isConsentSearch(raw: string | null | undefined): raw is string {
  if (!raw || !raw.startsWith('?')) return false;
  try {
    return new URLSearchParams(raw).has('client_id');
  } catch {
    return false;
  }
}

/** Called at boot, before MSAL: remember the request if that is where we are. */
export function capturePendingConsent(): string | null {
  try {
    if (window.location.pathname !== CONSENT_PATH) return null;
    const search = window.location.search;
    if (!isConsentSearch(search)) return null;
    store()?.setItem(KEY, search);
    return search;
  } catch {
    return null;
  }
}

export function readPendingConsent(): string | null {
  try {
    const v = store()?.getItem(KEY);
    return isConsentSearch(v) ? v : null;
  } catch {
    return null;
  }
}

export function clearPendingConsent(): void {
  try {
    store()?.removeItem(KEY);
  } catch {
    // ignore - a browser that refuses sessionStorage simply loses the replay
  }
}
