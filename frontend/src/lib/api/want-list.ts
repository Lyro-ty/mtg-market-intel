/**
 * Want List API functions
 */
import type {
  WantListItem,
  WantListListResponse,
  WantListItemCreate,
  WantListItemUpdate,
  WantListCheckPricesResponse,
  WantListPriority,
} from '@/types';
import { fetchApi } from './client';

export async function getWantList(options: {
  page?: number;
  pageSize?: number;
  priority?: WantListPriority;
} = {}): Promise<WantListListResponse> {
  const params = new URLSearchParams();

  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));
  if (options.priority) {
    params.set('priority', options.priority);
  }

  return fetchApi(`/want-list?${params}`, {}, true);
}

export async function getWantListItem(id: number): Promise<WantListItem> {
  return fetchApi(`/want-list/${id}`, {}, true);
}

export async function addToWantList(data: WantListItemCreate): Promise<WantListItem> {
  return fetchApi('/want-list', {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

export async function updateWantListItem(
  id: number,
  data: WantListItemUpdate
): Promise<WantListItem> {
  return fetchApi(`/want-list/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, true);
}

export async function deleteWantListItem(id: number): Promise<void> {
  await fetchApi(`/want-list/${id}`, {
    method: 'DELETE',
  }, true);
}

export async function checkWantListPrices(): Promise<WantListCheckPricesResponse> {
  return fetchApi('/want-list/check-prices', {
    method: 'POST',
  }, true);
}
