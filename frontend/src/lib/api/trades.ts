/**
 * Trades API functions for trade proposal management.
 */
import { fetchApi } from './client';
import type {
  TradeProposal,
  TradeListResponse,
  TradeStats,
} from '@/types';

// =============================================================================
// Request/Parameter Types
// =============================================================================

export interface TradeItemRequest {
  card_id: number;
  quantity?: number;
  condition?: string;
}

export interface CreateTradeRequest {
  recipient_id: number;
  proposer_items: TradeItemRequest[];
  recipient_items: TradeItemRequest[];
  message?: string;
}

export interface CounterTradeRequest {
  proposer_items: TradeItemRequest[];
  recipient_items: TradeItemRequest[];
  message?: string;
}

export interface TradeListParams {
  status?: string;
  direction?: 'sent' | 'received' | 'all';
  limit?: number;
  offset?: number;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get list of trade proposals for the current user.
 */
export async function getTrades(
  params: TradeListParams = {}
): Promise<TradeListResponse> {
  const searchParams = new URLSearchParams();

  if (params.status) {
    searchParams.append('status', params.status);
  }
  if (params.direction) {
    searchParams.append('direction', params.direction);
  }
  if (params.limit !== undefined) {
    searchParams.append('limit', params.limit.toString());
  }
  if (params.offset !== undefined) {
    searchParams.append('offset', params.offset.toString());
  }

  const queryString = searchParams.toString();
  const url = queryString ? `/trades?${queryString}` : '/trades';

  return fetchApi(url);
}

/**
 * Get a single trade proposal by ID.
 */
export async function getTrade(id: number): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}`);
}

/**
 * Create a new trade proposal.
 */
export async function createTrade(
  data: CreateTradeRequest
): Promise<TradeProposal> {
  return fetchApi('/trades', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Accept a trade proposal.
 */
export async function acceptTrade(id: number): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}/accept`, {
    method: 'POST',
  });
}

/**
 * Decline a trade proposal.
 */
export async function declineTrade(id: number): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}/decline`, {
    method: 'POST',
  });
}

/**
 * Cancel a trade proposal (proposer only).
 */
export async function cancelTrade(id: number): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}/cancel`, {
    method: 'POST',
  });
}

/**
 * Submit a counter-proposal for a trade.
 */
export async function counterTrade(
  id: number,
  data: CounterTradeRequest
): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}/counter`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Confirm completion of a trade.
 */
export async function confirmTrade(id: number): Promise<TradeProposal> {
  return fetchApi(`/trades/${id}/confirm`, {
    method: 'POST',
  });
}

/**
 * Get trade statistics for the current user.
 */
export async function getTradeStats(): Promise<TradeStats> {
  return fetchApi('/trades/stats/me');
}
