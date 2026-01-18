/**
 * Directory API functions for browsing and searching traders.
 */
import { fetchApi } from './client';

// ============ Types ============

export interface DirectoryUser {
  id: number;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  tagline?: string | null;
  card_type?: string | null;
  trade_count: number;
  reputation_score?: number | null;
  reputation_count: number;
  success_rate?: number | null;
  response_time_hours?: number | null;
  frame_tier: string;
  city?: string | null;
  country?: string | null;
  shipping_preference?: string | null;
  is_online: boolean;
  last_active_at?: string | null;
  open_to_trades: boolean;
  email_verified: boolean;
  discord_linked: boolean;
  id_verified: boolean;
  badges: Array<{ key: string; icon: string; name: string }>;
  formats: string[];
  signature_card?: { id: number; name: string; image_url?: string | null } | null;
  member_since: string;
}

export interface DirectoryResponse {
  users: DirectoryUser[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

export interface DirectorySearchParams {
  q?: string;
  sort?: 'discovery_score' | 'reputation' | 'trades' | 'newest' | 'best_match';
  reputation_tier?: string[];
  frame_tier?: string[];
  card_type?: string[];
  format?: string[];
  shipping?: string[];
  country?: string;
  online_only?: boolean;
  verified_only?: boolean;
  page?: number;
  limit?: number;
}

export interface SuggestedUser {
  user: DirectoryUser;
  reason: string;
  mutual_connection_count: number;
  matching_formats: string[];
  matching_cards: number;
}

export interface QuickSearchUser {
  id: number;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  frame_tier: string;
}

export interface TradePreview {
  user_id: number;
  cards_they_have_you_want: number;
  cards_they_have_you_want_value: number;
  cards_you_have_they_want: number;
  cards_you_have_they_want_value: number;
  is_mutual_match: boolean;
}

// ============ Favorites Types ============

export interface FavoriteUser {
  id: number;
  favorited_user_id: number;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  frame_tier: string;
  notify_on_listings: boolean;
  created_at: string;
}

export interface FavoritesListResponse {
  favorites: FavoriteUser[];
  total: number;
}

// ============ Directory Endpoints ============

/**
 * Get paginated directory listing with filters.
 */
export async function getDirectory(
  params: DirectorySearchParams = {}
): Promise<DirectoryResponse> {
  const searchParams = new URLSearchParams();

  if (params.q) searchParams.set('q', params.q);
  if (params.sort) searchParams.set('sort', params.sort);
  if (params.country) searchParams.set('country', params.country);
  if (params.online_only) searchParams.set('online_only', 'true');
  if (params.verified_only) searchParams.set('verified_only', 'true');
  if (params.page) searchParams.set('page', params.page.toString());
  if (params.limit) searchParams.set('limit', params.limit.toString());

  // Array parameters - append multiple times
  if (params.reputation_tier) {
    params.reputation_tier.forEach((tier) =>
      searchParams.append('reputation_tier', tier)
    );
  }
  if (params.frame_tier) {
    params.frame_tier.forEach((tier) =>
      searchParams.append('frame_tier', tier)
    );
  }
  if (params.card_type) {
    params.card_type.forEach((type) =>
      searchParams.append('card_type', type)
    );
  }
  if (params.format) {
    params.format.forEach((fmt) => searchParams.append('format', fmt));
  }
  if (params.shipping) {
    params.shipping.forEach((ship) =>
      searchParams.append('shipping', ship)
    );
  }

  const queryString = searchParams.toString();
  return fetchApi(`/directory${queryString ? `?${queryString}` : ''}`);
}

/**
 * Quick search for users by name (for autocomplete).
 */
export async function quickSearchUsers(
  query: string,
  limit: number = 10
): Promise<QuickSearchUser[]> {
  return fetchApi(
    `/directory/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}

/**
 * Get suggested connections for the current user.
 */
export async function getSuggestedUsers(
  limit: number = 10
): Promise<SuggestedUser[]> {
  return fetchApi(`/directory/suggested?limit=${limit}`);
}

/**
 * Get recently interacted users.
 */
export async function getRecentUsers(): Promise<DirectoryUser[]> {
  return fetchApi('/directory/recent');
}

/**
 * Get trade preview between current user and target user.
 */
export async function getTradePreview(userId: number): Promise<TradePreview> {
  return fetchApi(`/directory/${userId}/preview`);
}

// ============ Favorites Endpoints ============

/**
 * Get current user's list of favorited users.
 */
export async function getFavorites(): Promise<FavoritesListResponse> {
  return fetchApi('/favorites');
}

/**
 * Add a user to favorites.
 */
export async function addFavorite(
  userId: number,
  notifyOnListings: boolean = false
): Promise<{ status: string }> {
  return fetchApi(`/favorites/${userId}`, {
    method: 'POST',
    body: JSON.stringify({ notify_on_listings: notifyOnListings }),
  });
}

/**
 * Remove a user from favorites.
 */
export async function removeFavorite(
  userId: number
): Promise<{ status: string }> {
  return fetchApi(`/favorites/${userId}`, {
    method: 'DELETE',
  });
}

/**
 * Update favorite notification settings.
 */
export async function updateFavorite(
  userId: number,
  notifyOnListings: boolean
): Promise<{ status: string }> {
  return fetchApi(`/favorites/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify({ notify_on_listings: notifyOnListings }),
  });
}
