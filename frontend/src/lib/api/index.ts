/**
 * API client barrel export
 *
 * This file provides backwards compatibility by re-exporting all API functions.
 * For better tree-shaking, import directly from the specific module:
 *   import { getCard } from '@/lib/api/cards';
 *
 * Instead of:
 *   import { getCard } from '@/lib/api';
 */

// Core client
export {
  ApiError,
  API_BASE,
  fetchApi,
  getStoredToken,
  setStoredToken,
  clearStoredToken,
  checkHealth,
  getSiteStats,
} from './client';

export type { SiteStats } from './client';

// Authentication
export {
  login,
  register,
  getCurrentUser,
  updateProfile,
  changePassword,
  logout,
} from './auth';

// Cards
export {
  searchCards,
  getCard,
  refreshCard,
  getCardPrices,
  getCardHistory,
  getCardSignals,
  getCardMeta,
  getSimilarCards,
} from './cards';

// Market
export {
  getMarketOverview,
  getMarketIndex,
  getTopMovers,
  getVolumeByFormat,
  getColorDistribution,
} from './market';

// Recommendations
export {
  getRecommendations,
  getRecommendation,
  getCardRecommendations,
} from './recommendations';

// Dashboard
export {
  getDashboardSummary,
  getQuickStats,
} from './dashboard';

// Settings & Marketplaces
export {
  getSettings,
  updateSettings,
  getMarketplaces,
  toggleMarketplace,
} from './settings';

// Inventory
export {
  getInventoryMarketIndex,
  getInventoryTopMovers,
  importInventory,
  getInventory,
  getInventoryAnalytics,
  getInventoryItem,
  createInventoryItem,
  updateInventoryItem,
  deleteInventoryItem,
  getInventoryRecommendations,
  refreshInventoryValuations,
  runInventoryRecommendations,
  exportInventory,
} from './inventory';

// Tournaments
export {
  getTournaments,
  getTournament,
  getDecklist,
  getMetaCards,
} from './tournaments';

// Notifications
export {
  getNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from './notifications';

// Want List
export {
  getWantList,
  getWantListItem,
  addToWantList,
  updateWantListItem,
  deleteWantListItem,
  checkWantListPrices,
} from './want-list';

// Collection
export {
  getCollectionStats,
  refreshCollectionStats,
  getSetCompletions,
  getMilestones,
} from './collection';

// Imports
export {
  uploadImportFile,
  generateImportPreview,
  confirmImport,
  cancelImport,
  getImportJob,
  getImportJobs,
} from './imports';

// Portfolio
export {
  getPortfolioSummary,
  getPortfolioHistory,
  getPortfolioChartData,
  createPortfolioSnapshot,
} from './portfolio';

// Saved Searches
export {
  getSavedSearches,
  createSavedSearch,
  getSavedSearch,
  updateSavedSearch,
  deleteSavedSearch,
} from './saved-searches';

// News
export {
  getNews,
  getNewsArticle,
  getNewsSources,
  getCardNews,
} from './news';

// Spreads
export {
  getBuylistOpportunities,
  getSellingOpportunities,
  getArbitrageOpportunities,
  getSpreadMarketSummary,
} from './spreads';

// Connections
export {
  sendConnectionRequest,
  getPendingRequests,
  acceptConnectionRequest,
  declineConnectionRequest,
  cancelConnectionRequest,
  getConnections,
  removeConnection,
  checkConnectionStatus,
} from './connections';

export type {
  ConnectionRequest,
  ConnectionRequestorInfo,
  ConnectionRequestListResponse,
  SendConnectionRequestData,
} from './connections';

// Messages
export {
  sendMessage,
  getConversations,
  getConversation,
  getUnreadCount as getMessageUnreadCount,
  markMessageRead,
} from './messages';

export type {
  Message,
  ConversationSummary,
  ConversationListResponse,
  MessageListResponse,
  SendMessageData,
} from './messages';

// Quotes
export {
  createQuote,
  getQuotes,
  getQuote,
  updateQuote,
  deleteQuote,
  addQuoteItem,
  updateQuoteItem,
  deleteQuoteItem,
  bulkImportCards,
  getQuoteOffers,
  submitQuote,
  getMySubmissions,
  acceptCounterOffer,
  declineCounterOffer,
  exportQuoteCSV,
} from './quotes';

export type {
  Quote,
  QuoteItem,
  QuoteListResponse,
  StoreOffer,
  QuoteOffersPreview,
  QuoteSubmission,
  SubmissionListResponse,
  BulkImportResult,
} from './quotes';

// Trading Posts
export {
  registerTradingPost,
  getMyTradingPost,
  updateMyTradingPost,
  getNearbyTradingPosts,
  getTradingPost,
  createEvent,
  getMyEvents,
  updateEvent,
  deleteEvent,
  getTradingPostEvents,
  getNearbyEvents,
  getStoreSubmissions,
  getStoreSubmission,
  acceptSubmission,
  counterSubmission,
  declineSubmission,
} from './trading-posts';

export type {
  TradingPost,
  TradingPostPublic,
  TradingPostCreate,
  TradingPostUpdate,
  TradingPostListResponse,
  TradingPostEvent,
  EventCreate,
  EventUpdate,
  EventListResponse,
  StoreSubmission,
  StoreSubmissionListResponse,
} from './trading-posts';

// Trades
export {
  getTrades,
  getTrade,
  createTrade,
  acceptTrade,
  declineTrade,
  cancelTrade,
  counterTrade,
  confirmTrade,
  getTradeStats,
} from './trades';

export type {
  TradeItemRequest,
  CreateTradeRequest,
  CounterTradeRequest,
  TradeListParams,
} from './trades';

// Reputation
export {
  getMyReputation,
  getUserReputation,
  getUserReviews,
  createReview,
  getReputationLeaderboard,
} from './reputation';

export type { CreateReviewRequest } from './reputation';

// Discovery
export {
  getUsersWithMyWants,
  getUsersWhoWantMine,
  getMutualMatches,
  getTradeDetailsWithUser,
  getMyTradeableCards,
  getDiscoverySummary,
} from './discovery';

export type {
  UserMatch,
  MutualMatch,
  DiscoveryResponse,
  TradeCard,
  TradeUser,
  TradeSummary,
  TradeDetailsResponse,
  TradeableCard,
  TradeableCardsResponse,
  DiscoverySummary,
} from './discovery';

// Types re-exports for backwards compatibility
export type {
  ImportJob,
  ImportListResponse,
  PortfolioSnapshot,
  PortfolioSummary,
  PortfolioHistoryResponse,
  PortfolioChartData,
  SearchAlertFrequency,
  SavedSearch,
  SavedSearchListResponse,
  SavedSearchCreate,
  SavedSearchUpdate,
} from './types';

// Directory
export {
  getDirectory,
  quickSearchUsers,
  getSuggestedUsers,
  getRecentUsers,
  getTradePreview,
  getFavorites,
  addFavorite,
  removeFavorite,
  updateFavorite,
} from './directory';

export type {
  DirectoryUser,
  DirectoryResponse,
  DirectorySearchParams,
  SuggestedUser,
  QuickSearchUser,
  TradePreview,
  FavoriteUser,
  FavoritesListResponse,
} from './directory';

// Moderation (Admin)
export {
  getModerationQueue,
  getModerationStats,
  getCaseDetail,
  takeAction,
  getUserNotes,
  addUserNote,
  getAppeals,
  getAppeal,
  resolveAppeal,
  getDisputes,
  getDispute,
  assignDispute,
  resolveDispute,
} from './moderation';

export type {
  FlagLevel,
  FlagType,
  ModerationQueueItem,
  ModerationQueueResponse,
  ModerationStats,
  ReportInfo,
  AutoFlagInfo,
  PreviousActionInfo,
  ModNoteInfo,
  TradeStatsSummary,
  RecentTradeInfo,
  ReportedMessageInfo,
  TargetUserInfo,
  ModerationCaseDetail,
  ModerationActionResponse,
  AppealResponse,
  TradeDisputeResponse,
  TakeActionRequest,
  ResolveAppealRequest,
  ResolveDisputeRequest,
  AddModNoteRequest,
  ModerationQueueParams,
} from './moderation';
