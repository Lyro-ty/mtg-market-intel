/**
 * Platform Import API functions
 */
import { fetchApi, getStoredToken, ApiError, API_BASE } from './client';
import type { ImportJob, ImportListResponse } from './types';

export async function uploadImportFile(
  file: File,
  platform: 'moxfield' | 'archidekt' | 'deckbox' | 'tcgplayer' | 'generic_csv'
): Promise<ImportJob> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('platform', platform);

  const token = getStoredToken();
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }

  const response = await fetch(`${API_BASE}/imports/upload`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(errorData.detail || 'Upload failed', response.status);
  }

  return response.json();
}

export async function generateImportPreview(jobId: number): Promise<ImportJob> {
  return fetchApi(`/imports/${jobId}/preview`, {
    method: 'POST',
  }, true);
}

export async function confirmImport(
  jobId: number,
  skipUnmatched: boolean = true
): Promise<ImportJob> {
  return fetchApi(`/imports/${jobId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ skip_unmatched: skipUnmatched }),
  }, true);
}

export async function cancelImport(jobId: number): Promise<ImportJob> {
  return fetchApi(`/imports/${jobId}/cancel`, {
    method: 'POST',
  }, true);
}

export async function getImportJob(jobId: number): Promise<ImportJob> {
  return fetchApi(`/imports/${jobId}`, {}, true);
}

export async function getImportJobs(options: {
  limit?: number;
  offset?: number;
} = {}): Promise<ImportListResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) params.set('limit', String(options.limit));
  if (options.offset !== undefined) params.set('offset', String(options.offset));

  const queryString = params.toString();
  return fetchApi(`/imports${queryString ? `?${queryString}` : ''}`, {}, true);
}

// Re-export types for convenience
export type { ImportJob, ImportListResponse } from './types';
