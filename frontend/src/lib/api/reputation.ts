/**
 * Reputation API functions for user reputation and review management.
 */
import { fetchApi } from './client';
import type {
  Reputation,
  Review,
  ReviewListResponse,
  LeaderboardResponse,
} from '@/types';

// =============================================================================
// Request/Parameter Types
// =============================================================================

export interface CreateReviewRequest {
  reviewee_id: number;
  rating: number; // 1-5
  comment?: string;
  trade_id?: number;
  trade_type?: 'buy' | 'sell' | 'trade' | 'meetup';
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get the current user's reputation.
 * Requires authentication.
 */
export async function getMyReputation(): Promise<Reputation> {
  return fetchApi('/reputation/me', {}, true);
}

/**
 * Get a specific user's reputation by user ID.
 * Public endpoint.
 */
export async function getUserReputation(userId: number): Promise<Reputation> {
  return fetchApi(`/reputation/${userId}`);
}

/**
 * Get paginated reviews for a specific user.
 * Public endpoint.
 */
export async function getUserReviews(
  userId: number,
  limit: number = 20,
  offset: number = 0
): Promise<ReviewListResponse> {
  const searchParams = new URLSearchParams();

  if (limit !== 20) {
    searchParams.append('limit', limit.toString());
  }
  if (offset !== 0) {
    searchParams.append('offset', offset.toString());
  }

  const queryString = searchParams.toString();
  const url = queryString
    ? `/reputation/${userId}/reviews?${queryString}`
    : `/reputation/${userId}/reviews`;

  return fetchApi(url);
}

/**
 * Create a review for a user.
 * Requires authentication.
 */
export async function createReview(data: CreateReviewRequest): Promise<Review> {
  return fetchApi('/reputation/reviews', {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

/**
 * Get the reputation leaderboard with top traders.
 * Public endpoint.
 */
export async function getReputationLeaderboard(
  limit: number = 20,
  minReviews: number = 5
): Promise<LeaderboardResponse> {
  const searchParams = new URLSearchParams();

  if (limit !== 20) {
    searchParams.append('limit', limit.toString());
  }
  if (minReviews !== 5) {
    searchParams.append('min_reviews', minReviews.toString());
  }

  const queryString = searchParams.toString();
  const url = queryString ? `/reputation/leaderboard?${queryString}` : '/reputation/leaderboard';

  return fetchApi(url);
}
