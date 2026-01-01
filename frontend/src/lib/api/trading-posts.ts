/**
 * Trading Post (LGS) API functions
 */
import { fetchApi } from './client';

// ============ Types ============

export interface TradingPostCreate {
  store_name: string;
  description?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  phone?: string;
  website?: string;
  hours?: Record<string, string>;
  services?: string[];
  buylist_margin?: number;
}

export interface TradingPostUpdate {
  store_name?: string;
  description?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  phone?: string;
  website?: string;
  hours?: Record<string, string>;
  services?: string[];
  logo_url?: string;
  buylist_margin?: number;
}

export interface TradingPost {
  id: number;
  user_id: number;
  store_name: string;
  description: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string;
  postal_code: string | null;
  phone: string | null;
  website: string | null;
  hours: Record<string, string> | null;
  services: string[] | null;
  logo_url: string | null;
  buylist_margin: number;
  email_verified_at: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  is_verified: boolean;
  is_email_verified: boolean;
}

export interface TradingPostPublic {
  id: number;
  store_name: string;
  description: string | null;
  city: string | null;
  state: string | null;
  country: string;
  website: string | null;
  hours: Record<string, string> | null;
  services: string[] | null;
  logo_url: string | null;
  is_verified: boolean;
}

export interface TradingPostListResponse {
  items: TradingPostPublic[];
  total: number;
  page: number;
  page_size: number;
}

export interface TradingPostEvent {
  id: number;
  trading_post_id: number;
  title: string;
  description: string | null;
  event_type: 'tournament' | 'sale' | 'release' | 'meetup';
  format: string | null;
  start_time: string;
  end_time: string | null;
  entry_fee: number | null;
  max_players: number | null;
  created_at: string;
  updated_at: string;
  trading_post: TradingPostPublic | null;
}

export interface EventCreate {
  title: string;
  description?: string;
  event_type: 'tournament' | 'sale' | 'release' | 'meetup';
  format?: string;
  start_time: string;
  end_time?: string;
  entry_fee?: number;
  max_players?: number;
}

export interface EventUpdate {
  title?: string;
  description?: string;
  event_type?: 'tournament' | 'sale' | 'release' | 'meetup';
  format?: string;
  start_time?: string;
  end_time?: string;
  entry_fee?: number;
  max_players?: number;
}

export interface EventListResponse {
  items: TradingPostEvent[];
  total: number;
}

// ============ Trading Post CRUD ============

export async function registerTradingPost(
  data: TradingPostCreate
): Promise<TradingPost> {
  return fetchApi('/trading-posts/register', {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

export async function getMyTradingPost(): Promise<TradingPost> {
  return fetchApi('/trading-posts/me', {}, true);
}

export async function updateMyTradingPost(
  data: TradingPostUpdate
): Promise<TradingPost> {
  return fetchApi('/trading-posts/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  }, true);
}

export async function getNearbyTradingPosts(params?: {
  city?: string;
  state?: string;
  verified_only?: boolean;
  page?: number;
  page_size?: number;
}): Promise<TradingPostListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.city) searchParams.set('city', params.city);
  if (params?.state) searchParams.set('state', params.state);
  if (params?.verified_only !== undefined) {
    searchParams.set('verified_only', params.verified_only.toString());
  }
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

  const query = searchParams.toString();
  return fetchApi(`/trading-posts/nearby${query ? `?${query}` : ''}`);
}

export async function getTradingPost(id: number): Promise<TradingPostPublic> {
  return fetchApi(`/trading-posts/${id}`);
}

// ============ Events ============

export async function createEvent(data: EventCreate): Promise<TradingPostEvent> {
  return fetchApi('/trading-posts/me/events', {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

export async function getMyEvents(params?: {
  include_past?: boolean;
}): Promise<EventListResponse> {
  const query = params?.include_past ? '?include_past=true' : '';
  return fetchApi(`/trading-posts/me/events${query}`, {}, true);
}

export async function updateEvent(
  eventId: number,
  data: EventUpdate
): Promise<TradingPostEvent> {
  return fetchApi(`/trading-posts/me/events/${eventId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }, true);
}

export async function deleteEvent(eventId: number): Promise<void> {
  await fetchApi(`/trading-posts/me/events/${eventId}`, {
    method: 'DELETE',
  }, true);
}

export async function getTradingPostEvents(
  tradingPostId: number
): Promise<EventListResponse> {
  return fetchApi(`/trading-posts/${tradingPostId}/events`);
}

export async function getNearbyEvents(params?: {
  city?: string;
  state?: string;
  format?: string;
  event_type?: string;
  days?: number;
  limit?: number;
}): Promise<EventListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.city) searchParams.set('city', params.city);
  if (params?.state) searchParams.set('state', params.state);
  if (params?.format) searchParams.set('format', params.format);
  if (params?.event_type) searchParams.set('event_type', params.event_type);
  if (params?.days) searchParams.set('days', params.days.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchApi(`/events/nearby${query ? `?${query}` : ''}`);
}

// ============ Store Submissions ============

export interface StoreSubmission {
  id: number;
  quote_id: number;
  trading_post_id: number;
  status: 'pending' | 'accepted' | 'countered' | 'declined' | 'user_accepted' | 'user_declined';
  offer_amount: number;
  counter_amount: number | null;
  store_message: string | null;
  user_message: string | null;
  submitted_at: string;
  responded_at: string | null;
  quote_name: string | null;
  quote_item_count: number | null;
  quote_total_value: number | null;
}

export interface StoreSubmissionListResponse {
  items: StoreSubmission[];
  total: number;
}

export async function getStoreSubmissions(
  status?: string
): Promise<StoreSubmissionListResponse> {
  const query = status ? `?status=${status}` : '';
  return fetchApi(`/trading-posts/me/submissions${query}`, {}, true);
}

export async function getStoreSubmission(
  submissionId: number
): Promise<StoreSubmission> {
  return fetchApi(`/trading-posts/me/submissions/${submissionId}`, {}, true);
}

export async function acceptSubmission(
  submissionId: number
): Promise<{ status: string; offer_amount: number }> {
  return fetchApi(`/trading-posts/me/submissions/${submissionId}/accept`, {
    method: 'POST',
  }, true);
}

export async function counterSubmission(
  submissionId: number,
  data: { counter_amount: number; message?: string }
): Promise<{ status: string; counter_amount: number }> {
  return fetchApi(`/trading-posts/me/submissions/${submissionId}/counter`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

export async function declineSubmission(
  submissionId: number,
  message?: string
): Promise<{ status: string }> {
  const query = message ? `?message=${encodeURIComponent(message)}` : '';
  return fetchApi(`/trading-posts/me/submissions/${submissionId}/decline${query}`, {
    method: 'POST',
  }, true);
}
