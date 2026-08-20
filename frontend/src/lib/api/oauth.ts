import { BaseApiService } from './base';

/**
 * The two calls behind the connector consent screen.
 *
 * Everything else in the OAuth flow is spoken between the backend and
 * claude.ai directly (discovery, registration, /oauth/authorize,
 * /oauth/token). The browser only ever touches these two, and only after the
 * user is signed in - the request carries his Entra bearer like every other
 * API call, because approving a connector is a decision only a human may make.
 */
export interface OAuthConsentInput {
  clientId: string;
  redirectUri: string;
  state: string | null;
  codeChallenge: string;
  codeChallengeMethod: string;
  resource: string | null;
}

export interface OAuthRedirect {
  /** The client's OWN callback, built by the server. Never a URL we invent. */
  redirectUrl: string;
}

class OAuthApiService extends BaseApiService {
  constructor() {
    super('/api/oauth');
  }

  /** Approve: mints a ten-minute, single-use authorization code. */
  async consent(payload: OAuthConsentInput): Promise<OAuthRedirect> {
    return this.post('/consent', payload);
  }

  /**
   * Cancel. RFC 6749 4.1.2.1 - a refusal is still an answer, delivered to the
   * client's callback as error=access_denied so it can stop waiting.
   */
  async deny(payload: OAuthConsentInput): Promise<OAuthRedirect> {
    return this.post('/consent/deny', payload);
  }
}

export const oauthApi = new OAuthApiService();
