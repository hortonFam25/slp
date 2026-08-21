/**
 * Connection keys — the credential a machine presents at `/mcp`.
 *
 * Three routes, consumed by the "Connect Claude" settings page and nothing
 * else. They speak camelCase on the wire (see
 * `backend/app/schemas/api_token.py`), which is why these types are not in the
 * snake_case house style the rest of `lib/api` uses.
 *
 * The plaintext secret exists exactly once, in the 201 body of `createToken`.
 * The server keeps a sha256 digest and cannot produce it again, so a caller
 * that does not show it to the user has lost it.
 */

import { BaseApiService } from './base';
import { ApiError } from './errors';

/** How a key came to exist. */
export type ApiTokenKind = 'manual' | 'oauth';

export interface ApiToken {
  id: number;
  name: string;
  /** The literal first 12 characters ("slp_a1b2c3d4"), for display only. */
  prefix: string;
  createdAt: string | null;
  lastUsedAt: string | null;
  kind: ApiTokenKind | string;
  /** null = never expires. Manual keys are null; OAuth access keys are not. */
  expiresAt: string | null;
}

/** The 201 body. `token` is the only time the full secret is ever seen. */
export interface ApiTokenCreated extends ApiToken {
  token: string;
}

/** How many live MANUAL keys one user may hold. Mirrors `MAX_ACTIVE_TOKENS`. */
export const MAX_MANUAL_TOKENS = 10;

/**
 * True for the 409 the server raises when the manual-key cap is reached.
 *
 * The backend sends `detail: { message, code: "TOKEN_LIMIT" }` rather than a
 * bare string, so `ApiError.message` is unusable for this one case and the code
 * has to be read out of `details`.
 */
export function isTokenLimitError(error: unknown): boolean {
  if (!ApiError.isApiError(error) || error.status !== 409) return false;
  const detail = (error.details as { detail?: { code?: string } } | undefined)?.detail;
  return detail?.code === 'TOKEN_LIMIT';
}

/** The message the server sent with a TOKEN_LIMIT 409, or a sensible stand-in. */
export function tokenLimitMessage(error: unknown): string {
  if (ApiError.isApiError(error)) {
    const detail = (error.details as { detail?: { message?: string } } | undefined)?.detail;
    if (detail?.message) return detail.message;
  }
  return (
    `You already have ${MAX_MANUAL_TOKENS} connection keys. ` +
    'Revoke one before creating another.'
  );
}

class ApiTokensApiService extends BaseApiService {
  constructor() {
    super('/api/tokens');
  }

  /** This user's live connection keys, newest first. */
  async listTokens(): Promise<ApiToken[]> {
    return this.get<ApiToken[]>('');
  }

  /**
   * Mint a key. The returned `token` is the plaintext and will never be
   * available again — show it to the user before this promise's value is
   * discarded.
   *
   * Throws a 409 whose `isTokenLimitError` is true once the user holds
   * `MAX_MANUAL_TOKENS` live manual keys.
   */
  async createToken(name: string): Promise<ApiTokenCreated> {
    return this.post<ApiTokenCreated>('', { name });
  }

  /**
   * Revoke a key. 204, no body.
   *
   * Revoking an OAuth key cuts the whole grant — its refresh chain goes with
   * it, which is what makes "disconnect claude.ai" actually stick.
   */
  async revokeToken(id: number): Promise<void> {
    return this.delete<void>(`/${id}`);
  }
}

export const apiTokensApi = new ApiTokensApiService();
export default apiTokensApi;
