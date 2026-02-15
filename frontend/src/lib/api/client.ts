import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { ApiError, handleApiError } from './errors';
import { apiLogger } from '../utils/logger';

// Create axios instance with default config
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  withCredentials: true,
  timeout: 120000, // 2 minute timeout for large imports
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - for adding auth tokens, request logging, etc.
apiClient.interceptors.request.use(
  (config) => {
    // Auth token will be added per request via authorizedGet/authorizedPost functions
    // This allows for proper token refresh handling per request
    
    // Log requests in development
    apiLogger.apiRequest(config.method || 'UNKNOWN', config.url || 'unknown');
    
    return config;
  },
  (error) => {
    apiLogger.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

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


