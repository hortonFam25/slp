import { AxiosError } from 'axios';

import { DB_WAKE_EXHAUSTED } from '../db-wake/policy';

export class ApiError extends Error {
  public status: number;
  public details?: any;

  constructor(message: string, status: number, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }

  static fromAxiosError(error: AxiosError): ApiError {
    const status = error.response?.status || 500;
    const message = error.response?.data?.detail || error.message || 'An unknown error occurred';
    const details = error.response?.data;

    const apiError = new ApiError(message, status, details);

    // Carry the db-wake interceptor's "already waited two minutes on this"
    // marker across the AxiosError -> ApiError boundary. Without it the
    // TanStack Query retry rule cannot tell an untried failure from an
    // exhausted one, and would start a second retry storm behind the first.
    // See lib/db-wake/queryRetry.ts.
    if ((error as unknown as Record<string, unknown>)[DB_WAKE_EXHAUSTED]) {
      (apiError as unknown as Record<string, unknown>)[DB_WAKE_EXHAUSTED] = true;
    }

    return apiError;
  }

  static isApiError(error: any): error is ApiError {
    return error instanceof ApiError;
  }
}

export const handleApiError = (error: any): ApiError => {
  if (ApiError.isApiError(error)) {
    return error;
  }
  
  if (error.isAxiosError) {
    return ApiError.fromAxiosError(error);
  }
  
  return new ApiError('An unexpected error occurred', 500);
};

// Common error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network error. Please check your connection.',
  UNAUTHORIZED: 'You are not authorized to perform this action.',
  FORBIDDEN: 'Access forbidden.',
  NOT_FOUND: 'The requested resource was not found.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  SERVER_ERROR: 'Server error. Please try again later.',
} as const;
