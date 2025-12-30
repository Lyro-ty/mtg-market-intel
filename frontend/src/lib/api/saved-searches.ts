/**
 * Saved Searches API functions
 */
import { fetchApi } from './client';
import type {
  SavedSearch,
  SavedSearchListResponse,
  SavedSearchCreate,
  SavedSearchUpdate,
  SearchAlertFrequency,
} from './types';

export async function getSavedSearches(): Promise<SavedSearchListResponse> {
  return fetchApi('/saved-searches', {}, true);
}

export async function createSavedSearch(data: SavedSearchCreate): Promise<SavedSearch> {
  return fetchApi('/saved-searches', {
    method: 'POST',
    body: JSON.stringify(data),
  }, true);
}

export async function getSavedSearch(id: number): Promise<SavedSearch> {
  return fetchApi(`/saved-searches/${id}`, {}, true);
}

export async function updateSavedSearch(id: number, data: SavedSearchUpdate): Promise<SavedSearch> {
  return fetchApi(`/saved-searches/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }, true);
}

export async function deleteSavedSearch(id: number): Promise<void> {
  await fetchApi(`/saved-searches/${id}`, {
    method: 'DELETE',
  }, true);
}

// Re-export types for convenience
export type {
  SavedSearch,
  SavedSearchListResponse,
  SavedSearchCreate,
  SavedSearchUpdate,
  SearchAlertFrequency,
} from './types';
