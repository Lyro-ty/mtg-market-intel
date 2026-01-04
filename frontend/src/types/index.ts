/**
 * TypeScript types for the MTG Market Intel frontend
 *
 * This file re-exports types from the auto-generated OpenAPI types
 * and adds any frontend-only types not present in the API schema.
 *
 * To regenerate API types after backend schema changes:
 *   make generate-types
 *   # or: cd frontend && npm run generate-types
 */

// Re-export all generated types for advanced usage
export type { paths, components, operations } from './api.generated';

// Import components for aliasing
import type { components } from './api.generated';

// =============================================================================
// Type aliases for convenience - matches the API schema naming
// =============================================================================

// Auth types
export type User = components['schemas']['UserResponse'];
export type AuthToken = components['schemas']['Token'];
export type LoginCredentials = components['schemas']['UserLogin'];
export type RegisterData = components['schemas']['UserRegister'];

// Card types
export type Card = components['schemas']['CardResponse'];
export type CardSearchResult = components['schemas']['CardSearchResponse'];
export type CardDetail = components['schemas']['CardDetailResponse'];
export type CardPrices = components['schemas']['CardPriceResponse'];
export type CardHistory = components['schemas']['CardHistoryResponse'];
export type CardMetrics = components['schemas']['CardMetricsResponse'];

// Price types
export type MarketplacePrice = components['schemas']['MarketplacePriceDetail'];
export type PricePoint = components['schemas']['PricePoint'];

// Recommendation types
export type ActionType = components['schemas']['ActionType'];
// Extend RecommendationResponse with outcome tracking fields (may not be in API yet)
export type Recommendation = components['schemas']['RecommendationResponse'] & {
  outcome_evaluated_at?: string | null;
  outcome_price_end?: number | null;
  outcome_price_peak?: number | null;
  actual_profit_pct_end?: number | null;
  actual_profit_pct_peak?: number | null;
  accuracy_score_end?: number | null;
  accuracy_score_peak?: number | null;
};
export type RecommendationList = components['schemas']['RecommendationListResponse'];
export type RecommendationSummary = components['schemas']['RecommendationSummary'];

// Signal types
export type Signal = components['schemas']['SignalResponse'];
export type SignalSummary = components['schemas']['SignalSummary'];

// Dashboard types
export type DashboardSummary = components['schemas']['DashboardSummary'];
export type TopCard = components['schemas']['app__schemas__dashboard__TopCard'];
export type MarketSpread = components['schemas']['MarketSpread'];

// Settings types
export type Settings = components['schemas']['SettingsResponse'];
export type SettingsUpdate = components['schemas']['SettingsUpdate'];

// Marketplace types
export type Marketplace = components['schemas']['MarketplaceResponse'];

// Inventory types
export type InventoryCondition = components['schemas']['InventoryCondition'];
export type InventoryUrgency = components['schemas']['InventoryUrgency'];
export type InventoryItem = components['schemas']['InventoryItemResponse'];
export type InventoryListResponse = components['schemas']['InventoryListResponse'];
export type InventoryImportResponse = components['schemas']['InventoryImportResponse'];
export type InventoryAnalytics = components['schemas']['InventoryAnalytics'];
export type InventoryRecommendation = components['schemas']['InventoryRecommendationResponse'];
export type InventoryRecommendationList = components['schemas']['InventoryRecommendationListResponse'];

// Tournament types
export type Tournament = components['schemas']['TournamentResponse'];
export type TournamentListResponse = components['schemas']['TournamentListResponse'];
export type TournamentDetail = components['schemas']['TournamentDetailResponse'];
export type Standing = components['schemas']['StandingResponse'];
export type DecklistDetail = components['schemas']['DecklistDetailResponse'];
export type DecklistCard = components['schemas']['DecklistCardResponse'];
export type CardMetaStats = components['schemas']['CardMetaStatsResponse'];
export type MetaCardsListResponse = components['schemas']['MetaCardsListResponse'];
export type CardMetaResponse = components['schemas']['CardMetaResponse'];
export type MetaPeriod = components['schemas']['MetaPeriod'];

// Collection types
export type CollectionStats = components['schemas']['CollectionStatsResponse'];
export type SetCompletion = components['schemas']['SetCompletion'];
export type SetCompletionList = components['schemas']['SetCompletionList'];
export type Milestone = components['schemas']['MilestoneResponse'];
export type MilestoneList = components['schemas']['MilestoneList'];

// Notification types (type/priority are strings in the API, define literals here for frontend use)
export type NotificationType =
  | 'price_alert'
  | 'price_spike'
  | 'price_drop'
  | 'milestone'
  | 'system'
  | 'educational';
export type NotificationPriority = 'low' | 'medium' | 'high' | 'urgent';
export type Notification = components['schemas']['NotificationResponse'];
export type NotificationList = components['schemas']['NotificationList'];
export type UnreadCount = components['schemas']['UnreadCountResponse'];

// Want List types
export type WantListPriority = components['schemas']['WantListPriority'];
export type WantListItem = components['schemas']['WantListItemResponse'];
export type WantListItemCreate = components['schemas']['WantListItemCreate'];
export type WantListItemUpdate = components['schemas']['WantListItemUpdate'];
export type WantListListResponse = components['schemas']['WantListListResponse'];

// Want List Deal types (frontend-only, API returns inline)
export interface WantListDeal {
  id: number;
  card_id: number;
  card_name: string;
  set_code: string;
  target_price: number;
  current_price: number;
  savings: number;
  savings_pct: number;
  priority: WantListPriority;
}

export interface WantListCheckPricesResponse {
  message: string;
  deals: WantListDeal[];
  checked_count: number;
}

// Similar Cards types
export type SimilarCard = components['schemas']['SearchResult'];
export type SimilarCardsResponse = components['schemas']['SimilarCardsResponse'];

// News types (frontend definitions until API types are regenerated)
export interface NewsArticle {
  id: number;
  title: string;
  source: string;
  source_display: string;
  published_at: string | null;
  external_url: string;
  summary: string | null;
  card_mention_count: number;
}

export interface NewsArticleDetail extends NewsArticle {
  author: string | null;
  category: string | null;
  card_mentions: CardMention[];
}

export interface CardMention {
  card_id: number;
  card_name: string;
  context: string | null;
}

export interface NewsListResponse {
  items: NewsArticle[];
  total: number;
  has_more: boolean;
}

export interface NewsSource {
  source: string;
  display: string;
  count: number;
}

export interface CardNewsItem {
  id: number;
  title: string;
  source_display: string;
  published_at: string | null;
  external_url: string;
  context: string | null;
}

export interface CardNewsResponse {
  items: CardNewsItem[];
  total: number;
}

// Search types
export type AutocompleteSuggestion = components['schemas']['AutocompleteSuggestion'];
export type AutocompleteResponse = components['schemas']['AutocompleteResponse'];

// =============================================================================
// Frontend-only types (not in API schema)
// =============================================================================

// WebSocket channel types
export type WebSocketChannelType =
  | 'market'
  | 'card'
  | 'dashboard'
  | 'inventory'
  | 'recommendations';

export interface WebSocketMessage {
  type: string;
  channel?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface WebSocketSubscription {
  channel: WebSocketChannelType;
  params?: Record<string, string | number>;
}

export interface MarketUpdateMessage extends WebSocketMessage {
  type: 'market_update';
  index_value?: number;
  change_24h?: number;
  volume_24h?: number;
  currency?: string;
}

export interface CardUpdateMessage extends WebSocketMessage {
  type: 'card_update';
  card_id: number;
  price?: number;
  price_change?: number;
  marketplace_id?: number;
}

export interface DashboardUpdateMessage extends WebSocketMessage {
  type: 'dashboard_update';
  section: string;
  data?: Record<string, unknown>;
}

export interface InventoryUpdateMessage extends WebSocketMessage {
  type: 'inventory_update';
  item_id?: number;
  action?: 'created' | 'updated' | 'deleted';
  value_change?: number;
}

export interface RecommendationsUpdateMessage extends WebSocketMessage {
  type: 'recommendations_updated';
  count?: number;
  new_recommendations?: number;
}

// Decklist section type (frontend display)
export type DecklistSection = 'mainboard' | 'sideboard' | 'commander';

// Market page types (may differ from API - check if API has these)
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
  currency?: 'USD';
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

export interface ColorDistribution {
  window: '7d' | '30d';
  colors: string[];
  distribution: Record<string, number>;
  isMockData?: boolean;
}

// Import result type (for UI display)
export interface ImportedItem {
  line_number: number;
  raw_line: string;
  success: boolean;
  inventory_item_id?: number;
  card_id?: number;
  card_name?: string;
  error?: string;
}
