/**
 * Collection Stats API functions
 */
import type { CollectionStats, SetCompletionList, MilestoneList } from '@/types';
import { fetchApi } from './client';

export async function getCollectionStats(): Promise<CollectionStats> {
  return fetchApi('/collection/stats', {}, true);
}

export async function refreshCollectionStats(): Promise<{ status: string; message: string }> {
  return fetchApi('/collection/stats/refresh', {
    method: 'POST',
  }, true);
}

export async function getSetCompletions(options: {
  limit?: number;
  offset?: number;
  sortBy?: 'completion' | 'name';
} = {}): Promise<SetCompletionList> {
  const params = new URLSearchParams();

  if (options.limit !== undefined) params.set('limit', String(options.limit));
  if (options.offset !== undefined) params.set('offset', String(options.offset));
  if (options.sortBy) params.set('sort_by', options.sortBy);

  const queryString = params.toString();
  return fetchApi(`/collection/sets${queryString ? `?${queryString}` : ''}`, {}, true);
}

export async function getMilestones(): Promise<MilestoneList> {
  return fetchApi('/collection/milestones', {}, true);
}
