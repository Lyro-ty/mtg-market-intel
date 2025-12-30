/**
 * Portfolio API functions
 */
import { fetchApi } from './client';
import type {
  PortfolioSnapshot,
  PortfolioSummary,
  PortfolioHistoryResponse,
  PortfolioChartData,
} from './types';

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return fetchApi('/portfolio/summary', {}, true);
}

export async function getPortfolioHistory(days: number = 30): Promise<PortfolioHistoryResponse> {
  return fetchApi(`/portfolio/history?days=${days}`, {}, true);
}

export async function getPortfolioChartData(days: number = 30): Promise<PortfolioChartData> {
  return fetchApi(`/portfolio/chart-data?days=${days}`, {}, true);
}

export async function createPortfolioSnapshot(): Promise<PortfolioSnapshot> {
  return fetchApi('/portfolio/snapshot', {
    method: 'POST',
  }, true);
}

// Re-export types for convenience
export type {
  PortfolioSnapshot,
  PortfolioSummary,
  PortfolioHistoryResponse,
  PortfolioChartData,
} from './types';
