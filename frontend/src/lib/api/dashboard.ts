/**
 * Dashboard API functions
 */
import type { DashboardSummary } from '@/types';
import { fetchApi } from './client';

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
