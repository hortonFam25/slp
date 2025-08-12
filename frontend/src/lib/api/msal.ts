import { InteractionRequiredAuthError } from '@azure/msal-browser';
import { apiClient } from './client';
import type { IPublicClientApplication, SilentRequest } from '@azure/msal-browser';

export async function authorizedGet<T>(msal: IPublicClientApplication, url: string, scopes: string[]): Promise<T> {
  const account = msal.getActiveAccount() || msal.getAllAccounts()[0];
  if (!account) throw new Error('No active account');
  const request: SilentRequest = { account, scopes };
  try {
    const token = await msal.acquireTokenSilent(request);
    const res = await apiClient.get<T>(url, { headers: { Authorization: `Bearer ${token.accessToken}` } });
    return res.data;
  } catch (e) {
    if (e instanceof InteractionRequiredAuthError) {
      throw new Error('Interactive login required');
    }
    throw e;
  }
}


