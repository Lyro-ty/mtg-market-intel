/**
 * API client for the MTG Market Intel backend
 *
 * This file re-exports all API functions from the modular api/ directory.
 * For better tree-shaking, import directly from specific modules:
 *   import { getCard } from '@/lib/api/cards';
 *
 * The api/ directory is organized by domain:
 *   - client.ts: Core fetchApi, token management, ApiError
 *   - auth.ts: Authentication (login, register, logout)
 *   - cards.ts: Card search, details, history
 *   - market.ts: Market overview, top movers
 *   - inventory.ts: Inventory CRUD, analytics
 *   - recommendations.ts: Trading recommendations
 *   - tournaments.ts: Tournament data, meta cards
 *   - notifications.ts: User notifications
 *   - want-list.ts: Want list management
 *   - collection.ts: Collection stats
 *   - imports.ts: Platform imports
 *   - portfolio.ts: Portfolio tracking
 *   - saved-searches.ts: Saved searches
 *   - settings.ts: Settings, marketplaces
 */

export * from './api/index';
