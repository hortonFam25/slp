import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { ApiError, handleApiError } from './errors';
import { apiLogger } from '../utils/logger';
import type { IPublicClientApplication } from '@azure/msal-browser';
import { appScopes } from '../auth/authConfig';
// Imported from the module, not from `../db-wake` — the barrel also exports the
// pre-warm hook, which imports this file, and that would be a cycle.
import { installDbWakeInterceptor } from '../db-wake/interceptor';

// Create axios instance with default config
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  withCredentials: true,
  timeout: 120000, // 2 minute timeout for large imports
  headers: {
    'Content-Type': 'application/json',
  },
});

const getMsalInstance = (): IPublicClientApplication | undefined =>
  (window as unknown as { __msalInstance?: IPublicClientApplication }).__msalInstance;

export const getAccessToken = async (): Promise<string | null> => {
  const msal = getMsalInstance();
  if (!msal) {
    return null;
  }

  const account = msal.getActiveAccount() || msal.getAllAccounts()[0];
  if (!account) {
    return null;
  }

  try {
    const token = await msal.acquireTokenSilent({ account, scopes: appScopes });
    return token.accessToken;
  } catch {
    apiLogger.warn('Token acquisition skipped for request');
    return null;
  }
};

export const buildAuthenticatedFetchHeaders = async (
  headers: HeadersInit = {}
): Promise<Headers> => {
  const mergedHeaders = new Headers(headers);
  const token = await getAccessToken();
  if (token && !mergedHeaders.has('Authorization')) {
    mergedHeaders.set('Authorization', `Bearer ${token}`);
  }
  return mergedHeaders;
};

// Request interceptor - for adding auth tokens, request logging, etc.
apiClient.interceptors.request.use(
  async (config) => {
    const token = await getAccessToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }

    apiLogger.apiRequest(config.method || 'UNKNOWN', config.url || 'unknown');
    return config;
  },
  (error) => {
    apiLogger.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Azure SQL Serverless auto-pauses after 60 idle minutes, and the first request
// afterwards used to surface to the user as "Network Error". This interceptor
// absorbs that: it waits the database out and re-sends, so callers below only
// ever see a request that took a while.
//
// REGISTERED FIRST, AND THAT IS LOAD-BEARING. Axios runs response interceptors
// in registration order, and the handler below replaces the raw AxiosError with
// an ApiError — which has no `config`, so a retry could not be built from it.
// This one has to see the error while it is still re-sendable; anything it
// declines falls straight through to the ApiError mapping unchanged.
installDbWakeInterceptor(apiClient);

// Response interceptor - for global error handling, response transformation
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log successful responses in development
    apiLogger.apiResponse(response.status, response.config.url || 'unknown');
    
    return response;
  },
  (error) => {
    // Global error handling
    const apiError = handleApiError(error);
    
    // Log errors in development
    apiLogger.apiError(apiError.status, apiError.message);
    
    // Handle specific error cases globally
    switch (apiError.status) {
      case 401:
        // Handle unauthorized - redirect to login
        apiLogger.warn('Unauthorized access - redirecting to login');
        // window.location.href = '/login';
        break;
      case 403:
        // Handle forbidden
        apiLogger.warn('Access forbidden');
        break;
      case 500:
        // Handle server errors
        apiLogger.error('Server error occurred');
        break;
    }
    
    return Promise.reject(apiError);
  }
);

// Helper function for making typed API requests
export const makeApiRequest = async <T = any>(
  config: AxiosRequestConfig
): Promise<T> => {
  try {
    const response = await apiClient(config);
    return response.data;
  } catch (error) {
    throw handleApiError(error);
  }
};


