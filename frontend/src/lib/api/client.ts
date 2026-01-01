/**
 * Core API client - fetchApi, token management, and error handling
 */

// Use /api proxy when in browser, or direct URL when server-side or in development
const getApiBase = () => {
  if (typeof window !== 'undefined') {
    // Client-side: use Next.js rewrite proxy
    return process.env.NEXT_PUBLIC_API_URL || '/api';
  }
  // Server-side: use full URL
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

export const API_BASE = getApiBase();

// Token storage key
const TOKEN_KEY = 'auth_token';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

// Token management functions
export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {},
  requiresAuth: boolean = false
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add auth token if available
  const token = getStoredToken();
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  } else if (requiresAuth) {
    throw new ApiError('Authentication required', 401);
  }

  // Set timeout for long-running operations (like card refresh)
  // Default to 5 minutes for refresh endpoints, 30 seconds for others
  const isRefreshEndpoint = endpoint.includes('/refresh');
  const timeoutMs = isRefreshEndpoint ? 5 * 60 * 1000 : 30 * 1000;

  try {
    // Create an AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetail = 'Unknown error';
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || JSON.stringify(errorData);
      } catch {
        // If response is not JSON, try to get text
        try {
          errorDetail = await response.text() || `HTTP ${response.status}`;
        } catch {
          errorDetail = `HTTP ${response.status} ${response.statusText}`;
        }
      }

      // Clear token if unauthorized
      if (response.status === 401) {
        clearStoredToken();
      }

      throw new ApiError(errorDetail, response.status);
    }

    // Handle empty responses
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const text = await response.text();
      if (!text) {
        return {} as T;
      }
      return JSON.parse(text);
    }

    return response.json();
  } catch (error) {
    // Handle timeout/abort errors
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(
        `Request timeout: The operation took too long to complete. ${isRefreshEndpoint ? 'Try refreshing in the background or check backend logs.' : ''}`,
        408
      );
    }

    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(
        `Network error: Unable to connect to API at ${url}. Please check if the backend is running.`,
        0
      );
    }

    // Re-throw ApiError as-is
    if (error instanceof ApiError) {
      throw error;
    }

    // Wrap other errors
    throw new ApiError(
      error instanceof Error ? error.message : 'Request failed',
      0
    );
  }
}

// Health check
export async function checkHealth(): Promise<{ status: string }> {
  return fetchApi('/health');
}

// Site stats for landing page
export interface SiteStats {
  seekers: number;
  trading_posts: number;
  cards_in_vault: number;
}

export async function getSiteStats(): Promise<SiteStats> {
  return fetchApi('/stats');
}
