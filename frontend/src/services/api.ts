import { ApiResponse } from '../types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: any;

  constructor(message: string, status: number, code?: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

class ApiClient {
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include', // Exclusively use secure HttpOnly cookies
      });
    } catch (err: any) {
      // Network failure or backend offline - do not crash silently
      throw new ApiError(
        'Backend service unreachable. Please ensure the server is running.',
        0,
        'NETWORK_ERROR'
      );
    }

    let payload: any;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError(
        `Server returned ${response.status} ${response.statusText}`,
        response.status,
        `HTTP_${response.status}`
      );
    }

    if (!response.ok || payload?.success === false) {
      const errorMsg =
        payload?.error?.message ||
        payload?.detail ||
        `HTTP ${response.status} Request failed`;

      throw new ApiError(
        errorMsg,
        response.status,
        payload?.error?.code,
        payload?.error?.details
      );
    }

    return (payload?.data !== undefined ? payload.data : payload) as T;
  }

  get<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined>,
    options?: RequestInit,
  ): Promise<T> {
    let url = endpoint;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, val]) => {
        if (val !== undefined && val !== null && val !== '') {
          searchParams.append(key, String(val));
        }
      });
      const qs = searchParams.toString();
      if (qs) {
        url += (url.includes('?') ? '&' : '?') + qs;
      }
    }
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  post<T>(endpoint: string, body?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  put<T>(endpoint: string, body?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  patch<T>(endpoint: string, body?: any, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }
}

export const api = new ApiClient();
