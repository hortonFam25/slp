import { AxiosRequestConfig } from 'axios';
import { makeApiRequest } from './client';
import { BaseQueryParams, PaginatedResponse } from './types';

export abstract class BaseApiService {
  protected baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  // Generic GET request
  protected async get<T>(
    endpoint: string = '',
    params?: Record<string, any>
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: 'GET',
      url: `${this.baseUrl}${endpoint}`,
      params,
    };
    
    return makeApiRequest<T>(config);
  }

  // Generic POST request
  protected async post<T>(
    endpoint: string = '',
    data?: any
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: 'POST',
      url: `${this.baseUrl}${endpoint}`,
      data,
    };
    
    return makeApiRequest<T>(config);
  }

  // Generic PUT request
  protected async put<T>(
    endpoint: string = '',
    data?: any
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: 'PUT',
      url: `${this.baseUrl}${endpoint}`,
      data,
    };
    
    return makeApiRequest<T>(config);
  }

  // Generic PATCH request
  protected async patch<T>(
    endpoint: string = '',
    data?: any
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: 'PATCH',
      url: `${this.baseUrl}${endpoint}`,
      data,
    };
    
    return makeApiRequest<T>(config);
  }

  // Generic DELETE request
  protected async delete<T = void>(
    endpoint: string = ''
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: 'DELETE',
      url: `${this.baseUrl}${endpoint}`,
    };
    
    return makeApiRequest<T>(config);
  }

  // Helper for building query parameters
  protected buildQueryParams(params: BaseQueryParams): Record<string, any> {
    const queryParams: Record<string, any> = {};
    
    if (params.page !== undefined) queryParams.page = params.page;
    if (params.limit !== undefined) queryParams.limit = params.limit;
    if (params.sort) queryParams.sort = params.sort;
    if (params.order) queryParams.order = params.order;
    
    return queryParams;
  }

  // Helper for paginated requests
  protected async getPaginated<T>(
    endpoint: string = '',
    params: BaseQueryParams = {}
  ): Promise<PaginatedResponse<T>> {
    const queryParams = this.buildQueryParams(params);
    return this.get<PaginatedResponse<T>>(endpoint, queryParams);
  }
}
