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
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(error.detail || 'Request failed', response.status);
  }
  
  return response.json();
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
  options: { marketplaces?: string[]; sync?: boolean } = {}
): Promise<CardDetail> {
  const { marketplaces, sync = true } = options;
  const params = new URLSearchParams();
  params.set('sync', String(sync));
  
  return fetchApi(`/cards/${cardId}/refresh?${params}`, {
    method: 'POST',
    body: JSON.stringify({ marketplaces }),
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

// Export error class for use in components
export { ApiError };

