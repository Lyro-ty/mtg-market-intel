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

// Authentication types
export interface User {
  id: number;
  email: string;
  username: string;
  display_name?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  display_name?: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// Inventory types
export type InventoryCondition = 
  | 'MINT'
  | 'NEAR_MINT'
  | 'LIGHTLY_PLAYED'
  | 'MODERATELY_PLAYED'
  | 'HEAVILY_PLAYED'
  | 'DAMAGED';

export type InventoryUrgency = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';

export interface InventoryItem {
  id: number;
  card_id: number;
  card_name: string;
  card_set: string;
  card_image_url?: string;
  quantity: number;
  condition: InventoryCondition;
  is_foil: boolean;
  language: string;
  acquisition_price?: number;
  acquisition_currency: string;
  acquisition_date?: string;
  acquisition_source?: string;
  current_value?: number;
  value_change_pct?: number;
  last_valued_at?: string;
  profit_loss?: number;
  profit_loss_pct?: number;
  import_batch_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface InventoryListResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  total_items: number;
  total_quantity: number;
  total_value: number;
  total_acquisition_cost: number;
  total_profit_loss: number;
  total_profit_loss_pct?: number;
}

export interface ImportedItem {
  line_number: number;
  raw_line: string;
  success: boolean;
  inventory_item_id?: number;
  card_id?: number;
  card_name?: string;
  error?: string;
}

export interface InventoryImportResponse {
  batch_id: string;
  total_lines: number;
  successful_imports: number;
  failed_imports: number;
  items: ImportedItem[];
}

export interface InventoryAnalytics {
  total_unique_cards: number;
  total_quantity: number;
  total_acquisition_cost: number;
  total_current_value: number;
  total_profit_loss: number;
  profit_loss_pct?: number;
  condition_breakdown: Record<string, number>;
  top_gainers: InventoryItem[];
  top_losers: InventoryItem[];
  value_distribution: Record<string, number>;
  sell_recommendations: number;
  hold_recommendations: number;
  critical_alerts: number;
}

export interface InventoryRecommendation {
  id: number;
  inventory_item_id: number;
  card_id: number;
  card_name: string;
  card_set: string;
  card_image_url?: string;
  action: ActionType;
  urgency: InventoryUrgency;
  confidence: number;
  horizon_days: number;
  current_price?: number;
  target_price?: number;
  potential_profit_pct?: number;
  acquisition_price?: number;
  roi_from_acquisition?: number;
  rationale: string;
  suggested_marketplace?: string;
  suggested_listing_price?: number;
  valid_until?: string;
  is_active: boolean;
  created_at: string;
}

export interface InventoryRecommendationList {
  recommendations: InventoryRecommendation[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  critical_count: number;
  high_count: number;
  normal_count: number;
  low_count: number;
  sell_count: number;
  hold_count: number;
}

// Market types
export interface MarketOverview {
  totalCardsTracked: number;
  totalListings: number | null;
  volume24hUsd: number;
  avgPriceChange24hPct: number | null;
  activeFormatsTracked: number;
}

export interface MarketIndexPoint {
  timestamp: string;
  indexValue: number;
}

export interface MarketIndex {
  range: '7d' | '30d' | '90d' | '1y';
  points: MarketIndexPoint[];
  isMockData?: boolean;
}

export interface TopMover {
  cardName: string;
  setCode: string;
  format: string;
  currentPriceUsd: number;
  changePct: number;
  volume: number;
}

export interface TopMovers {
  window: '24h' | '7d';
  gainers: TopMover[];
  losers: TopMover[];
  isMockData?: boolean;
}

export interface VolumeByFormatPoint {
  timestamp: string;
  volume: number;
}

export interface FormatVolume {
  format: string;
  data: VolumeByFormatPoint[];
}

export interface VolumeByFormat {
  days: number;
  formats: FormatVolume[];
  isMockData?: boolean;
}

