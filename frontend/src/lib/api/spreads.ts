/**
 * Spread analysis API functions
 */
import { fetchApi } from './client';

export interface BuylistOpportunity {
  card_id: number;
  card_name: string;
  set_code: string;
  image_url: string | null;
  retail_price: number;
  buylist_price: number;
  vendor: string;
  spread: number;
  spread_pct: number;
  credit_price: number | null;
  credit_spread_pct: number | null;
}

export interface ArbitrageOpportunity {
  card_id: number;
  card_name: string;
  set_code: string;
  image_url: string | null;
  buy_marketplace: string;
  buy_price: number;
  sell_marketplace: string;
  sell_price: number;
  profit: number;
  profit_pct: number;
}

export interface BuylistOpportunitiesResponse {
  opportunities: BuylistOpportunity[];
  total: number;
}

export interface ArbitrageOpportunitiesResponse {
  opportunities: ArbitrageOpportunity[];
  total: number;
}

export interface SpreadMarketSummary {
  cards_with_buylist_data: number;
  average_spread_pct: number | null;
  sample_size: number;
  data_freshness_hours: number;
  last_updated: string;
}

/**
 * Get best buylist opportunities (cards with high spread)
 */
export async function getBuylistOpportunities(params?: {
  limit?: number;
  min_spread_pct?: number;
  min_price?: number;
  vendor?: string;
}): Promise<BuylistOpportunitiesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.min_spread_pct) searchParams.set('min_spread_pct', String(params.min_spread_pct));
  if (params?.min_price) searchParams.set('min_price', String(params.min_price));
  if (params?.vendor) searchParams.set('vendor', params.vendor);

  const query = searchParams.toString();
  return fetchApi(`/spreads/best-buylist-opportunities${query ? `?${query}` : ''}`);
}

/**
 * Get best selling opportunities (cards with low spread - good to sell)
 */
export async function getSellingOpportunities(params?: {
  limit?: number;
  max_spread_pct?: number;
  min_buylist?: number;
}): Promise<BuylistOpportunitiesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.max_spread_pct) searchParams.set('max_spread_pct', String(params.max_spread_pct));
  if (params?.min_buylist) searchParams.set('min_buylist', String(params.min_buylist));

  const query = searchParams.toString();
  return fetchApi(`/spreads/best-selling-opportunities${query ? `?${query}` : ''}`);
}

/**
 * Get cross-marketplace arbitrage opportunities
 */
export async function getArbitrageOpportunities(params?: {
  limit?: number;
  min_profit_pct?: number;
  min_profit?: number;
}): Promise<ArbitrageOpportunitiesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.min_profit_pct) searchParams.set('min_profit_pct', String(params.min_profit_pct));
  if (params?.min_profit) searchParams.set('min_profit', String(params.min_profit));

  const query = searchParams.toString();
  return fetchApi(`/spreads/arbitrage-opportunities${query ? `?${query}` : ''}`);
}

/**
 * Get spread market summary statistics
 */
export async function getSpreadMarketSummary(): Promise<SpreadMarketSummary> {
  return fetchApi('/spreads/market-summary');
}
