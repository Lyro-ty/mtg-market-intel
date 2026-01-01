/**
 * Trade Quotes API functions
 */
import { fetchApi } from './client';

// ============ Types ============

export interface QuoteItem {
  id: number;
  card_id: number;
  card_name: string;
  set_code: string | null;
  quantity: number;
  condition: string;
  market_price: number | null;
  line_total: number | null;
}

export interface Quote {
  id: number;
  user_id: number;
  name: string | null;
  status: 'draft' | 'submitted' | 'completed' | 'expired';
  total_market_value: number | null;
  item_count: number;
  items: QuoteItem[];
  created_at: string;
  updated_at: string;
}

export interface QuoteListResponse {
  items: Quote[];
  total: number;
  page: number;
  page_size: number;
}

export interface StoreOffer {
  trading_post_id: number;
  store_name: string;
  city: string | null;
  state: string | null;
  is_verified: boolean;
  buylist_margin: number;
  offer_amount: number;
}

export interface QuoteOffersPreview {
  quote_id: number;
  total_market_value: number;
  offers: StoreOffer[];
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

export interface QuoteSubmission {
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
  trading_post: TradingPostPublic | null;
  quote_name: string | null;
  quote_item_count: number | null;
  quote_total_value: number | null;
}

export interface SubmissionListResponse {
  items: QuoteSubmission[];
  total: number;
}

export interface BulkImportResult {
  imported: number;
  failed: number;
  errors: string[];
}

// ============ Quote CRUD ============

export async function createQuote(name?: string): Promise<Quote> {
  return fetchApi('/quotes', {
    method: 'POST',
    body: JSON.stringify({ name }),
  }, true);
}

export async function getQuotes(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<QuoteListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.page) searchParams.set('page', params.page.toString());
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

  const query = searchParams.toString();
  return fetchApi(`/quotes/my${query ? `?${query}` : ''}`, {}, true);
}

export async function getQuote(quoteId: number): Promise<Quote> {
  return fetchApi(`/quotes/${quoteId}`, {}, true);
}

export async function updateQuote(quoteId: number, data: {
  name?: string;
  status?: string;
}): Promise<Quote> {
  return fetchApi(`/quotes/${quoteId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }, true);
}

export async function deleteQuote(quoteId: number): Promise<void> {
  await fetchApi(`/quotes/${quoteId}`, {
    method: 'DELETE',
  }, true);
}

// ============ Quote Items ============

export async function addQuoteItem(quoteId: number, data: {
  card_id: number;
  quantity?: number;
  condition?: string;
}): Promise<QuoteItem> {
  return fetchApi(`/quotes/${quoteId}/items`, {
    method: 'POST',
    body: JSON.stringify({
      card_id: data.card_id,
      quantity: data.quantity ?? 1,
      condition: data.condition ?? 'NM',
    }),
  }, true);
}

export async function updateQuoteItem(quoteId: number, itemId: number, data: {
  quantity?: number;
  condition?: string;
}): Promise<QuoteItem> {
  return fetchApi(`/quotes/${quoteId}/items/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }, true);
}

export async function deleteQuoteItem(quoteId: number, itemId: number): Promise<void> {
  await fetchApi(`/quotes/${quoteId}/items/${itemId}`, {
    method: 'DELETE',
  }, true);
}

export async function bulkImportCards(quoteId: number, items: Array<{
  card_name: string;
  set_code?: string;
  quantity?: number;
  condition?: string;
}>): Promise<BulkImportResult> {
  return fetchApi(`/quotes/${quoteId}/import`, {
    method: 'POST',
    body: JSON.stringify({ items }),
  }, true);
}

// ============ Offers & Submission ============

export async function getQuoteOffers(quoteId: number, params?: {
  city?: string;
  state?: string;
  limit?: number;
}): Promise<QuoteOffersPreview> {
  const searchParams = new URLSearchParams();
  if (params?.city) searchParams.set('city', params.city);
  if (params?.state) searchParams.set('state', params.state);
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchApi(`/quotes/${quoteId}/offers${query ? `?${query}` : ''}`, {}, true);
}

export async function submitQuote(quoteId: number, data: {
  trading_post_ids: number[];
  message?: string;
}): Promise<QuoteSubmission[]> {
  return fetchApi(`/quotes/${quoteId}/submit`, {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

// ============ User Submissions ============

export async function getMySubmissions(status?: string): Promise<SubmissionListResponse> {
  const query = status ? `?status=${status}` : '';
  return fetchApi(`/quotes/submissions/my${query}`, {}, true);
}

export async function acceptCounterOffer(submissionId: number): Promise<{ status: string; message: string }> {
  return fetchApi(`/quotes/submissions/${submissionId}/accept-counter`, {
    method: 'POST',
  }, true);
}

export async function declineCounterOffer(submissionId: number): Promise<{ status: string; message: string }> {
  return fetchApi(`/quotes/submissions/${submissionId}/decline-counter`, {
    method: 'POST',
  }, true);
}
