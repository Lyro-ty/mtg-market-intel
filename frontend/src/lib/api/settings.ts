/**
 * Settings and Marketplaces API functions
 */
import type { Settings, SettingsUpdate, Marketplace } from '@/types';
import { fetchApi } from './client';

// Settings API
export async function getSettings(): Promise<Settings> {
  return fetchApi('/settings');
}

export async function updateSettings(updates: SettingsUpdate): Promise<Settings> {
  return fetchApi('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

// Marketplaces API
export async function getMarketplaces(
  enabledOnly: boolean = true
): Promise<{ marketplaces: Marketplace[]; total: number }> {
  return fetchApi(`/marketplaces?enabled_only=${enabledOnly}`);
}

export async function toggleMarketplace(
  marketplaceId: number
): Promise<{ marketplace_id: number; is_enabled: boolean }> {
  return fetchApi(`/marketplaces/${marketplaceId}/toggle`, {
    method: 'PATCH',
  });
}
