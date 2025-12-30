/**
 * Local API types that aren't in the generated types
 */
import type { SimilarCardsResponse as GlobalSimilarCardsResponse } from '@/types';

// Re-export from global types for convenience
export type SimilarCardsResponse = GlobalSimilarCardsResponse;

// Import Job types
export interface ImportJob {
  id: number;
  platform: string;
  status: string;
  filename: string;
  file_size: number;
  total_rows: number;
  matched_cards: number;
  unmatched_cards: number;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  error_message?: string;
  preview_data?: {
    items: Array<{
      row_number: number;
      card_name: string;
      set_code?: string;
      set_name?: string;
      collector_number?: string;
      quantity: number;
      condition: string;
      is_foil: boolean;
      language: string;
      acquisition_price?: number;
      matched_card_id?: number;
      match_confidence: number;
      match_error?: string;
    }>;
    total: number;
    matched: number;
    unmatched: number;
  };
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface ImportListResponse {
  items: ImportJob[];
  total: number;
  limit: number;
  offset: number;
}

// Portfolio types
export interface PortfolioSnapshot {
  id: number;
  snapshot_date: string;
  total_value: number;
  total_cost: number;
  total_cards: number;
  unique_cards: number;
  value_change_1d?: number;
  value_change_7d?: number;
  value_change_30d?: number;
  value_change_pct_1d?: number;
  value_change_pct_7d?: number;
  value_change_pct_30d?: number;
  breakdown?: {
    foil: number;
    non_foil: number;
    by_set: Record<string, number>;
  };
  top_gainers?: Array<{
    card_id: number;
    card_name: string;
    set_code: string;
    current_value: number;
    change_pct: number;
  }>;
  top_losers?: Array<{
    card_id: number;
    card_name: string;
    set_code: string;
    current_value: number;
    change_pct: number;
  }>;
}

export interface PortfolioSummary {
  total_value: number;
  total_cost: number;
  total_cards: number;
  unique_cards: number;
  profit_loss: number;
  profit_loss_pct: number;
  value_change_1d?: number;
  value_change_7d?: number;
  value_change_30d?: number;
  value_change_pct_1d?: number;
  value_change_pct_7d?: number;
  value_change_pct_30d?: number;
  top_gainers?: PortfolioSnapshot['top_gainers'];
  top_losers?: PortfolioSnapshot['top_losers'];
}

export interface PortfolioHistoryResponse {
  snapshots: PortfolioSnapshot[];
  days: number;
}

export interface PortfolioChartData {
  labels: string[];
  values: number[];
  costs: number[];
}

// Saved Search types
export type SearchAlertFrequency = 'never' | 'daily' | 'weekly';

export interface SavedSearch {
  id: number;
  name: string;
  query?: string;
  filters?: Record<string, unknown>;
  alert_enabled: boolean;
  alert_frequency: SearchAlertFrequency;
  price_alert_threshold?: number;
  last_run_at?: string;
  last_result_count: number;
  created_at: string;
}

export interface SavedSearchListResponse {
  items: SavedSearch[];
  total: number;
}

export interface SavedSearchCreate {
  name: string;
  query?: string;
  filters?: Record<string, unknown>;
  alert_enabled?: boolean;
  alert_frequency?: SearchAlertFrequency;
  price_alert_threshold?: number;
}

export interface SavedSearchUpdate {
  name?: string;
  query?: string;
  filters?: Record<string, unknown>;
  alert_enabled?: boolean;
  alert_frequency?: SearchAlertFrequency;
  price_alert_threshold?: number;
}
