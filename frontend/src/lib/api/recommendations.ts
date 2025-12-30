/**
 * Recommendations API functions
 */
import type { Recommendation, RecommendationList } from '@/types';
import { fetchApi } from './client';

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
