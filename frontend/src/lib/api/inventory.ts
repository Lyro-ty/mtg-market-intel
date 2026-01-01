/**
 * Inventory API functions
 */
import type {
  MarketIndex,
  InventoryItem,
  InventoryListResponse,
  InventoryImportResponse,
  InventoryAnalytics,
  InventoryRecommendationList,
  InventoryCondition,
  InventoryUrgency,
  ActionType,
} from '@/types';
import { fetchApi, getStoredToken, ApiError, API_BASE } from './client';

// Inventory dashboard API
export async function getInventoryMarketIndex(
  range: '7d' | '30d' | '90d' | '1y' = '7d',
  isFoil?: boolean
): Promise<MarketIndex> {
  const params = new URLSearchParams({ range, currency: 'USD' });
  if (isFoil !== undefined) {
    params.append('is_foil', String(isFoil));
  }
  return fetchApi(`/inventory/market-index?${params.toString()}`, {}, true);
}

export async function getInventoryTopMovers(
  window: '24h' | '7d' = '24h'
): Promise<{ window: string; gainers: Array<{
  card_id: number;
  card_name: string;
  set_code: string;
  image_url?: string;
  old_price: number;
  new_price: number;
  change_pct: number;
}>; losers: Array<{
  card_id: number;
  card_name: string;
  set_code: string;
  image_url?: string;
  old_price: number;
  new_price: number;
  change_pct: number;
}>; data_freshness_hours: number }> {
  return fetchApi(`/inventory/top-movers?window=${window}`, {}, true);
}

// Inventory CRUD API
export async function importInventory(
  content: string,
  options: {
    format?: 'csv' | 'plaintext' | 'auto';
    hasHeader?: boolean;
    defaultCondition?: InventoryCondition;
    defaultAcquisitionSource?: string;
  } = {}
): Promise<InventoryImportResponse> {
  return fetchApi('/inventory/import', {
    method: 'POST',
    body: JSON.stringify({
      content,
      format: options.format || 'auto',
      has_header: options.hasHeader ?? true,
      default_condition: options.defaultCondition || 'NEAR_MINT',
      default_acquisition_source: options.defaultAcquisitionSource,
    }),
  }, true);
}

export async function getInventory(options: {
  search?: string;
  setCode?: string;
  condition?: InventoryCondition;
  isFoil?: boolean;
  minValue?: number;
  maxValue?: number;
  sortBy?: 'created_at' | 'current_value' | 'value_change_pct' | 'card_name' | 'quantity';
  sortOrder?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
} = {}): Promise<InventoryListResponse> {
  const params = new URLSearchParams();

  if (options.search) params.set('search', options.search);
  if (options.setCode) params.set('set_code', options.setCode);
  if (options.condition) params.set('condition', options.condition);
  if (options.isFoil !== undefined) params.set('is_foil', String(options.isFoil));
  if (options.minValue !== undefined) params.set('min_value', String(options.minValue));
  if (options.maxValue !== undefined) params.set('max_value', String(options.maxValue));
  if (options.sortBy) params.set('sort_by', options.sortBy);
  if (options.sortOrder) params.set('sort_order', options.sortOrder);
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));

  return fetchApi(`/inventory?${params}`, {}, true);
}

export async function getInventoryAnalytics(): Promise<InventoryAnalytics> {
  return fetchApi('/inventory/analytics', {}, true);
}

export async function getInventoryItem(itemId: number): Promise<InventoryItem> {
  return fetchApi(`/inventory/${itemId}`, {}, true);
}

export async function createInventoryItem(item: {
  card_id: number;
  quantity?: number;
  condition?: InventoryCondition;
  is_foil?: boolean;
  language?: string;
  acquisition_price?: number;
  acquisition_currency?: string;
  acquisition_date?: string;
  acquisition_source?: string;
  notes?: string;
}): Promise<InventoryItem> {
  return fetchApi('/inventory', {
    method: 'POST',
    body: JSON.stringify(item),
  }, true);
}

export async function updateInventoryItem(
  itemId: number,
  updates: Partial<{
    quantity: number;
    condition: InventoryCondition;
    is_foil: boolean;
    language: string;
    acquisition_price: number;
    acquisition_currency: string;
    acquisition_date: string;
    acquisition_source: string;
    notes: string;
  }>
): Promise<InventoryItem> {
  return fetchApi(`/inventory/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }, true);
}

export async function deleteInventoryItem(itemId: number): Promise<void> {
  return fetchApi(`/inventory/${itemId}`, {
    method: 'DELETE',
  }, true);
}

export async function getInventoryRecommendations(options: {
  action?: ActionType;
  urgency?: InventoryUrgency;
  minConfidence?: number;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
} = {}): Promise<InventoryRecommendationList> {
  const params = new URLSearchParams();

  if (options.action) params.set('action', options.action);
  if (options.urgency) params.set('urgency', options.urgency);
  if (options.minConfidence !== undefined) params.set('min_confidence', String(options.minConfidence));
  if (options.isActive !== undefined) params.set('is_active', String(options.isActive));
  params.set('page', String(options.page || 1));
  params.set('page_size', String(options.pageSize || 20));

  return fetchApi(`/inventory/recommendations/list?${params}`, {}, true);
}

export async function refreshInventoryValuations(): Promise<{
  message: string;
  updated_count: number;
}> {
  return fetchApi('/inventory/refresh-valuations', {
    method: 'POST',
  }, true);
}

export async function runInventoryRecommendations(itemIds?: number[]): Promise<{
  date: string;
  items_processed: number;
  total_recommendations: number;
  sell_recommendations: number;
  hold_recommendations: number;
  critical_alerts: number;
  high_priority: number;
  errors: number;
}> {
  return fetchApi('/inventory/run-recommendations', {
    method: 'POST',
    body: JSON.stringify(itemIds ? { item_ids: itemIds } : {}),
  }, true);
}

export async function exportInventory(format: 'csv' | 'txt' | 'cardtrader' = 'csv'): Promise<void> {
  const url = `${API_BASE}/inventory/export?format=${format}`;
  const token = getStoredToken();

  if (!token) {
    throw new ApiError('Authentication required', 401);
  }

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Export failed: ${response.statusText}`, response.status);
  }

  // Get the blob and trigger download
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;

  // Get filename from Content-Disposition header or use default
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `inventory.${format === 'cardtrader' ? 'csv' : format}`;
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }

  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(downloadUrl);
}
