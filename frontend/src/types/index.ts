/**
 * TypeScript types for the MTG Market Intel frontend
 */

// Card types
export interface Card {
  id: number;
  scryfall_id: string;
  oracle_id?: string;
  name: string;
  set_code: string;
  set_name?: string;
  collector_number: string;
  rarity?: string;
  mana_cost?: string;
  cmc?: number;
  type_line?: string;
  oracle_text?: string;
  power?: string;
  toughness?: string;
  image_url?: string;
  image_url_small?: string;
}

export interface CardSearchResult {
  cards: Card[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// Price types
export interface MarketplacePrice {
  marketplace_id: number;
  marketplace_name: string;
  marketplace_slug: string;
  price: number;
  currency: string;
  price_foil?: number;
  num_listings?: number;
  last_updated: string;
}

export interface CardPrices {
  card_id: number;
  card_name: string;
  prices: MarketplacePrice[];
  lowest_price?: number;
  highest_price?: number;
  spread_pct?: number;
  updated_at: string;
}

export interface PricePoint {
  date: string;
  price: number;
  marketplace: string;
  currency: string;
  min_price?: number;
  max_price?: number;
  num_listings?: number;
}

export interface CardHistory {
  card_id: number;
  card_name: string;
  history: PricePoint[];
  from_date: string;
  to_date: string;
  data_points: number;
}

// Metrics types
export interface CardMetrics {
  card_id: number;
  date: string;
  avg_price?: number;
  min_price?: number;
  max_price?: number;
  spread_pct?: number;
  price_change_7d?: number;
  price_change_30d?: number;
  volatility_7d?: number;
  ma_7d?: number;
  ma_30d?: number;
  total_listings?: number;
}

// Signal types
export interface Signal {
  id: number;
  card_id: number;
  date: string;
  signal_type: string;
  value?: number;
  confidence?: number;
  details?: Record<string, unknown>;
  llm_insight?: string;
  llm_provider?: string;
}

export interface SignalSummary {
  signal_type: string;
  value?: number;
  confidence?: number;
  date: string;
  llm_insight?: string;
}

// Recommendation types
export type ActionType = 'BUY' | 'SELL' | 'HOLD';

export interface Recommendation {
  id: number;
  card_id: number;
  card_name: string;
  card_set: string;
  card_image_url?: string;
  marketplace_id?: number;
  marketplace_name?: string;
  action: ActionType;
  confidence: number;
  horizon_days: number;
  target_price?: number;
  current_price?: number;
  potential_profit_pct?: number;
  rationale: string;
  source_signals?: string[];
  valid_until?: string;
  is_active: boolean;
  created_at: string;
}

export interface RecommendationList {
  recommendations: Recommendation[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  buy_count: number;
  sell_count: number;
  hold_count: number;
}

export interface RecommendationSummary {
  action: ActionType;
  confidence: number;
  rationale: string;
  marketplace?: string;
  potential_profit_pct?: number;
}

// Dashboard types
export interface TopCard {
  card_id: number;
  card_name: string;
  set_code: string;
  image_url?: string;
  current_price?: number;
  price_change_pct: number;
  price_change_period: string;
}

export interface MarketSpread {
  card_id: number;
  card_name: string;
  set_code: string;
  image_url?: string;
  lowest_price: number;
  lowest_marketplace: string;
  highest_price: number;
  highest_marketplace: string;
  spread_pct: number;
}

export interface DashboardSummary {
  total_cards: number;
  total_with_prices: number;
  total_marketplaces: number;
  top_gainers: TopCard[];
  top_losers: TopCard[];
  highest_spreads: MarketSpread[];
  total_recommendations: number;
  buy_recommendations: number;
  sell_recommendations: number;
  hold_recommendations: number;
  last_scrape_time?: string;
  last_analytics_time?: string;
  avg_price_change_7d?: number;
  avg_spread_pct?: number;
}

// Card detail types
export interface CardDetail {
  card: Card;
  metrics?: CardMetrics;
  current_prices: MarketplacePrice[];
  recent_signals: SignalSummary[];
  active_recommendations: RecommendationSummary[];
  refresh_requested?: boolean;
  refresh_reason?: string | null;
}

// Settings types
export interface Settings {
  settings: Record<string, unknown>;
  enabled_marketplaces: string[];
  min_roi_threshold: number;
  min_confidence_threshold: number;
  recommendation_horizon_days: number;
  price_history_days: number;
  scraping_enabled: boolean;
  analytics_enabled: boolean;
}

export interface SettingsUpdate {
  enabled_marketplaces?: string[];
  min_roi_threshold?: number;
  min_confidence_threshold?: number;
  recommendation_horizon_days?: number;
  price_history_days?: number;
  scraping_enabled?: boolean;
  analytics_enabled?: boolean;
}

// Marketplace types
export interface Marketplace {
  id: number;
  name: string;
  slug: string;
  base_url: string;
  is_enabled: boolean;
  supports_api: boolean;
  default_currency: string;
}

