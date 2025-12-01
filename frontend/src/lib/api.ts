/**
 * API client for the MTG Market Intel backend
 */

import type {
  Card,
  CardSearchResult,
  CardDetail,
  CardPrices,
  CardHistory,
  Recommendation,
  RecommendationList,
  DashboardSummary,
  Settings,
  SettingsUpdate,
  Marketplace,
  Signal,
  MarketOverview,
  MarketIndex,
  TopMovers,
  VolumeByFormat,
  User,
  LoginCredentials,
  RegisterData,
  AuthToken,
  InventoryItem,
  InventoryListResponse,
  InventoryImportResponse,
  InventoryAnalytics,
  InventoryRecommendationList,
  InventoryCondition,
  InventoryUrgency,
  ActionType,
} from '@/types';

// Use /api proxy when in browser, or direct URL when server-side or in development
const getApiBase = () => {
  if (typeof window !== 'undefined') {
    // Client-side: use Next.js rewrite proxy
    return process.env.NEXT_PUBLIC_API_URL || '/api';
  }
  // Server-side: use full URL
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};

const API_BASE = getApiBase();

// Token storage key
const TOKEN_KEY = 'auth_token';

class ApiError extends Error {
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

async function fetchApi<T>(
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
  
  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });
    
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

// Authentication API
export async function login(credentials: LoginCredentials): Promise<AuthToken> {
  const token = await fetchApi<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
  setStoredToken(token.access_token);
  return token;
}

export async function register(data: RegisterData): Promise<User> {
  return fetchApi<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getCurrentUser(): Promise<User> {
  return fetchApi<User>('/auth/me', {}, true);
}

export async function updateProfile(updates: { display_name?: string }): Promise<User> {
  return fetchApi<User>('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }, true);
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await fetchApi('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  }, true);
}

export async function logout(): Promise<void> {
  try {
    await fetchApi('/auth/logout', { method: 'POST' }, true);
  } finally {
    clearStoredToken();
  }
}

// Health check
export async function checkHealth(): Promise<{ status: string }> {
  return fetchApi('/health');
}

// Cards API
export async function searchCards(
  query: string,
  options: {
    setCode?: string;
    page?: number;
    pageSize?: number;
  } = {}
): Promise<CardSearchResult> {
  const params = new URLSearchParams({
    q: query,
    page: String(options.page || 1),
    page_size: String(options.pageSize || 20),
  });
  
  if (options.setCode) {
    params.set('set_code', options.setCode);
  }
  
  return fetchApi(`/cards/search?${params}`);
}

export async function getCard(cardId: number): Promise<CardDetail> {
  return fetchApi(`/cards/${cardId}`);
}

export async function refreshCard(
  cardId: number,
  options: {
    marketplaces?: string[];
    sync?: boolean;
  } = {}
): Promise<CardDetail> {
  const params = new URLSearchParams();
  if (options.sync !== undefined) {
    params.set('sync', String(options.sync));
  }
  
  const queryString = params.toString();
  return fetchApi(`/cards/${cardId}/refresh${queryString ? `?${queryString}` : ''}`, {
    method: 'POST',
    body: JSON.stringify({ marketplaces: options.marketplaces }),
  });
}

export async function getCardPrices(cardId: number): Promise<CardPrices> {
  return fetchApi(`/cards/${cardId}/prices`);
}

export async function getCardHistory(
  cardId: number,
  options: {
    days?: number;
    marketplaceId?: number;
  } = {}
): Promise<CardHistory> {
  const params = new URLSearchParams();
  
  if (options.days) {
    params.set('days', String(options.days));
  }
  if (options.marketplaceId) {
    params.set('marketplace_id', String(options.marketplaceId));
  }
  
  const queryString = params.toString();
  return fetchApi(`/cards/${cardId}/history${queryString ? `?${queryString}` : ''}`);
}

export async function getCardSignals(
  cardId: number,
  days: number = 7
): Promise<{ card_id: number; signals: Signal[]; total: number }> {
  return fetchApi(`/cards/${cardId}/signals?days=${days}`);
}

// Recommendations API
export async function getRecommendations(options: {
  action?: 'BUY' | 'SELL' | 'HOLD';
  minConfidence?: number;
  marketplaceId?: number;
  setCode?: string;
  minPrice?: number;
  maxPrice?: number;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
} = {}): Promise<RecommendationList> {
  const params = new URLSearchParams();
  
  if (options.action) params.set('action', options.action);
  if (options.minConfidence !== undefined) params.set('min_confidence', String(options.minConfidence));
  if (options.marketplaceId) params.set('marketplace_id', String(options.marketplaceId));
  if (options.setCode) params.set('set_code', options.setCode);
  if (options.minPrice !== undefined) params.set('min_price', String(options.minPrice));
  if (options.maxPrice !== undefined) params.set('max_price', String(options.maxPrice));
  if (options.isActive !== undefined) params.set('is_active', String(options.isActive));
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));
  
  return fetchApi(`/recommendations?${params}`);
}

export async function getRecommendation(id: number): Promise<Recommendation> {
  return fetchApi(`/recommendations/${id}`);
}

export async function getCardRecommendations(
  cardId: number,
  isActive: boolean = true
): Promise<RecommendationList> {
  return fetchApi(`/recommendations/card/${cardId}?is_active=${isActive}`);
}

// Dashboard API
export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchApi('/dashboard/summary');
}

export async function getQuickStats(): Promise<{
  total_cards: number;
  tracked_cards: number;
  active_recommendations: number;
  avg_price_change_7d: number;
}> {
  return fetchApi('/dashboard/stats');
}

// Settings API
export async function getSettings(): Promise<Settings> {
  return fetchApi('/settings');
}

export async function updateSettings(updates: SettingsUpdate): Promise<Settings> {
  return fetchApi('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

// Marketplaces API
export async function getMarketplaces(
  enabledOnly: boolean = true
): Promise<{ marketplaces: Marketplace[]; total: number }> {
  return fetchApi(`/marketplaces?enabled_only=${enabledOnly}`);
}

export async function toggleMarketplace(
  marketplaceId: number
): Promise<{ marketplace_id: number; is_enabled: boolean }> {
  return fetchApi(`/marketplaces/${marketplaceId}/toggle`, {
    method: 'PATCH',
  });
}

// Market API
export async function getMarketOverview(): Promise<MarketOverview> {
  return fetchApi('/market/overview');
}

export async function getMarketIndex(
  range: '7d' | '30d' | '90d' | '1y' = '7d'
): Promise<MarketIndex> {
  return fetchApi(`/market/index?range=${range}`);
}

export async function getTopMovers(
  window: '24h' | '7d' = '24h'
): Promise<TopMovers> {
  return fetchApi(`/market/top-movers?window=${window}`);
}

export async function getVolumeByFormat(
  days: number = 30
): Promise<VolumeByFormat> {
  return fetchApi(`/market/volume-by-format?days=${days}`);
}

// Inventory API (requires authentication)
export async function importInventory(
  content: string,
  options: {
    format?: 'csv' | 'plaintext' | 'auto';
    hasHeader?: boolean;
    defaultCondition?: InventoryCondition;
    defaultAcquisitionSource?: string;
  } = {}
): Promise<InventoryImportResponse> {
  return fetchApi('/inventory/import', {
    method: 'POST',
    body: JSON.stringify({
      content,
      format: options.format || 'auto',
      has_header: options.hasHeader ?? true,
      default_condition: options.defaultCondition || 'NEAR_MINT',
      default_acquisition_source: options.defaultAcquisitionSource,
    }),
  }, true);
}

export async function getInventory(options: {
  search?: string;
  setCode?: string;
  condition?: InventoryCondition;
  isFoil?: boolean;
  minValue?: number;
  maxValue?: number;
  sortBy?: 'created_at' | 'current_value' | 'value_change_pct' | 'card_name' | 'quantity';
  sortOrder?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
} = {}): Promise<InventoryListResponse> {
  const params = new URLSearchParams();
  
  if (options.search) params.set('search', options.search);
  if (options.setCode) params.set('set_code', options.setCode);
  if (options.condition) params.set('condition', options.condition);
  if (options.isFoil !== undefined) params.set('is_foil', String(options.isFoil));
  if (options.minValue !== undefined) params.set('min_value', String(options.minValue));
  if (options.maxValue !== undefined) params.set('max_value', String(options.maxValue));
  if (options.sortBy) params.set('sort_by', options.sortBy);
  if (options.sortOrder) params.set('sort_order', options.sortOrder);
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));
  
  return fetchApi(`/inventory?${params}`, {}, true);
}

export async function getInventoryAnalytics(): Promise<InventoryAnalytics> {
  return fetchApi('/inventory/analytics', {}, true);
}

export async function getInventoryItem(itemId: number): Promise<InventoryItem> {
  return fetchApi(`/inventory/${itemId}`, {}, true);
}

export async function createInventoryItem(item: {
  card_id: number;
  quantity?: number;
  condition?: InventoryCondition;
  is_foil?: boolean;
  language?: string;
  acquisition_price?: number;
  acquisition_currency?: string;
  acquisition_date?: string;
  acquisition_source?: string;
  notes?: string;
}): Promise<InventoryItem> {
  return fetchApi('/inventory', {
    method: 'POST',
    body: JSON.stringify(item),
  }, true);
}

export async function updateInventoryItem(
  itemId: number,
  updates: Partial<{
    quantity: number;
    condition: InventoryCondition;
    is_foil: boolean;
    language: string;
    acquisition_price: number;
    acquisition_currency: string;
    acquisition_date: string;
    acquisition_source: string;
    notes: string;
  }>
): Promise<InventoryItem> {
  return fetchApi(`/inventory/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }, true);
}

export async function deleteInventoryItem(itemId: number): Promise<void> {
  return fetchApi(`/inventory/${itemId}`, {
    method: 'DELETE',
  }, true);
}

export async function getInventoryRecommendations(options: {
  action?: ActionType;
  urgency?: InventoryUrgency;
  minConfidence?: number;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
} = {}): Promise<InventoryRecommendationList> {
  const params = new URLSearchParams();
  
  if (options.action) params.set('action', options.action);
  if (options.urgency) params.set('urgency', options.urgency);
  if (options.minConfidence !== undefined) params.set('min_confidence', String(options.minConfidence));
  if (options.isActive !== undefined) params.set('is_active', String(options.isActive));
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));
  
  return fetchApi(`/inventory/recommendations/list?${params}`, {}, true);
}

export async function refreshInventoryValuations(): Promise<{
  message: string;
  updated_count: number;
}> {
  return fetchApi('/inventory/refresh-valuations', {
    method: 'POST',
  }, true);
}

export async function runInventoryRecommendations(itemIds?: number[]): Promise<{
  date: string;
  items_processed: number;
  total_recommendations: number;
  sell_recommendations: number;
  hold_recommendations: number;
  critical_alerts: number;
  high_priority: number;
  errors: number;
}> {
  return fetchApi('/inventory/run-recommendations', {
    method: 'POST',
    body: JSON.stringify(itemIds ? { item_ids: itemIds } : {}),
  }, true);
}

// Export error class for use in components
export { ApiError };

