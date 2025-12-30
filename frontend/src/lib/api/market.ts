/**
 * Market API functions
 */
import type { MarketOverview, MarketIndex, TopMovers, VolumeByFormat, ColorDistribution } from '@/types';
import { fetchApi } from './client';

export async function getMarketOverview(): Promise<MarketOverview> {
  return fetchApi('/market/overview');
}

export async function getMarketIndex(
  range: '7d' | '30d' | '90d' | '1y' = '7d',
  isFoil?: boolean
): Promise<MarketIndex> {
  const params = new URLSearchParams({ range, currency: 'USD' });
  if (isFoil !== undefined) {
    params.append('is_foil', String(isFoil));
  }
  return fetchApi(`/market/index?${params.toString()}`);
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

export async function getColorDistribution(
  window: '7d' | '30d' = '7d'
): Promise<ColorDistribution> {
  return fetchApi(`/market/color-distribution?window=${window}`);
}
