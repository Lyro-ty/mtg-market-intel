/**
 * Discovery API functions for finding trading partners.
 */
import { fetchApi } from './client';

// =============================================================================
// Types
// =============================================================================

export interface UserMatch {
  user_id: number;
  username: string;
  display_name: string | null;
  location: string | null;
  avatar_url: string | null;
  matching_cards: number;
  card_names: string[];
}

export interface MutualMatch {
  user_id: number;
  username: string;
  display_name: string | null;
  location: string | null;
  avatar_url: string | null;
  cards_they_have_i_want: number;
  cards_i_have_they_want: number;
  total_matching_cards: number;
}

export interface DiscoveryResponse {
  matches: UserMatch[] | MutualMatch[];
  total: number;
}

export interface TradeCard {
  card_id: number;
  name: string;
  set_code: string;
  image_url_small: string | null;
  quantity: number;
  condition: string;
  is_foil: boolean;
  target_price: number | null;
}

export interface TradeUser {
  user_id: number;
  username: string;
  display_name: string | null;
  location: string | null;
  avatar_url: string | null;
}

export interface TradeSummary {
  cards_i_can_get: number;
  cards_i_can_give: number;
  is_mutual: boolean;
}

export interface TradeDetailsResponse {
  other_user: TradeUser;
  cards_they_have_i_want: TradeCard[];
  cards_i_have_they_want: TradeCard[];
  trade_summary: TradeSummary;
}

export interface TradeableCard {
  card_id: number;
  name: string;
  set_code: string;
  image_url_small: string | null;
  quantity: number;
  condition: string;
  is_foil: boolean;
  current_value: number | null;
  users_who_want_it: number;
}

export interface TradeableCardsResponse {
  cards: TradeableCard[];
  total: number;
}

export interface DiscoverySummary {
  tradeable_cards: number;
  want_list_items: number;
  users_with_my_wants: number;
  mutual_matches: number;
  discovery_score: number;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Find users who have cards I want.
 */
export async function getUsersWithMyWants(
  limit: number = 20
): Promise<DiscoveryResponse> {
  return fetchApi(`/discovery/users-with-my-wants?limit=${limit}`, {}, true);
}

/**
 * Find users who want my tradeable cards.
 */
export async function getUsersWhoWantMine(
  limit: number = 20
): Promise<DiscoveryResponse> {
  return fetchApi(`/discovery/users-who-want-mine?limit=${limit}`, {}, true);
}

/**
 * Find mutual matches where both parties can benefit.
 */
export async function getMutualMatches(
  limit: number = 20
): Promise<DiscoveryResponse> {
  return fetchApi(`/discovery/mutual-matches?limit=${limit}`, {}, true);
}

/**
 * Get detailed trade information with a specific user.
 */
export async function getTradeDetailsWithUser(
  userId: number
): Promise<TradeDetailsResponse> {
  return fetchApi(`/discovery/trade-details/${userId}`, {}, true);
}

/**
 * Get my cards that are available for trade.
 */
export async function getMyTradeableCards(
  limit: number = 50
): Promise<TradeableCardsResponse> {
  return fetchApi(`/discovery/my-tradeable-cards?limit=${limit}`, {}, true);
}

/**
 * Get discovery summary/stats.
 */
export async function getDiscoverySummary(): Promise<DiscoverySummary> {
  return fetchApi('/discovery/summary', {}, true);
}
