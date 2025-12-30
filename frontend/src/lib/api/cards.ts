/**
 * Cards API functions
 */
import type { CardSearchResult, CardDetail, CardPrices, CardHistory, Signal, CardMetaResponse } from '@/types';
import { fetchApi } from './client';
import type { SimilarCardsResponse } from './types';

export async function searchCards(
  query: string,
  options: {
    setCode?: string;
    page?: number;
    pageSize?: number;
  } = {}
): Promise<CardSearchResult> {
  const params = new URLSearchParams({
    q: query,
    page: String(options.page || 1),
    page_size: String(options.pageSize || 20),
  });

  if (options.setCode) {
    params.set('set_code', options.setCode);
  }

  return fetchApi(`/cards/search?${params}`);
}

export async function getCard(cardId: number): Promise<CardDetail> {
  return fetchApi(`/cards/${cardId}`);
}

export async function refreshCard(
  cardId: number,
  options: {
    marketplaces?: string[];
    sync?: boolean;
    force?: boolean;
  } = {}
): Promise<CardDetail> {
  const params = new URLSearchParams();
  if (options.sync !== undefined) {
    params.set('sync', String(options.sync));
  }
  if (options.force !== undefined) {
    params.set('force', String(options.force));
  }

  const queryString = params.toString();
  return fetchApi(`/cards/${cardId}/refresh${queryString ? `?${queryString}` : ''}`, {
    method: 'POST',
    body: JSON.stringify({ marketplaces: options.marketplaces }),
  });
}

export async function getCardPrices(cardId: number): Promise<CardPrices> {
  return fetchApi(`/cards/${cardId}/prices`);
}

export async function getCardHistory(
  cardId: number,
  options: {
    days?: number;
    marketplaceId?: number;
    condition?: string;
    isFoil?: boolean;
  } = {}
): Promise<CardHistory> {
  const params = new URLSearchParams();

  if (options.days) {
    params.set('days', String(options.days));
  }
  if (options.marketplaceId) {
    params.set('marketplace_id', String(options.marketplaceId));
  }
  if (options.condition) {
    params.set('condition', options.condition);
  }
  if (options.isFoil !== undefined) {
    params.set('is_foil', String(options.isFoil));
  }

  const queryString = params.toString();
  return fetchApi(`/cards/${cardId}/history${queryString ? `?${queryString}` : ''}`);
}

export async function getCardSignals(
  cardId: number,
  days: number = 7
): Promise<{ card_id: number; signals: Signal[]; total: number }> {
  return fetchApi(`/cards/${cardId}/signals?days=${days}`);
}

export async function getCardMeta(cardId: number): Promise<CardMetaResponse> {
  return fetchApi(`/cards/${cardId}/meta`);
}

export async function getSimilarCards(
  cardId: number,
  limit: number = 8
): Promise<SimilarCardsResponse> {
  return fetchApi(`/search/similar/${cardId}?limit=${limit}`);
}
