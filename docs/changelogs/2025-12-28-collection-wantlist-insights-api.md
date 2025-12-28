# Collection, Want List & Insights API - Changelog

**Date:** 2025-12-28
**Branch:** `feature/collection-wantlist-insights-api`
**Commits:** 26

## Summary

This release adds complete backend APIs and frontend integration for the Collection, Want List, and Insights pages. Users can now track cards they want to acquire with price targets, receive notifications when prices drop, view collection statistics and set completion progress, and earn milestones for collection achievements.

---

## New Features

### Want List System
- **Add cards to want list** with target prices and priority levels (low/medium/high)
- **Price alerts** - get notified when card prices drop to or below your target
- **On-demand price check** - manually trigger a scan to find deals
- **Full CRUD operations** - add, update, delete want list items

### Unified Notification System
- **6 notification types**: Price Alert, Price Spike, Price Drop, Milestone, System, Educational
- **4 priority levels**: Low, Medium, High, Urgent
- **Deduplication** - prevents duplicate notifications within 24 hours
- **Read/unread tracking** with timestamps
- **Bulk operations** - mark all as read

### Collection Statistics
- **Cached stats** for performance (total cards, unique cards, total value)
- **Set completion tracking** - see progress for each MTG set you own
- **On-demand refresh** with background recalculation
- **Stale detection** - automatic recalculation when inventory changes

### Milestones & Achievements
- **Cards owned milestones**: 10, 50, 100, 250, 500, 1000, 2500, 5000
- **Collection value milestones**: $100, $500, $1000, $2500, $5000, $10000
- **Sets started milestones**: 5, 10, 25, 50
- **Automatic notifications** when milestones are achieved

### MTG Sets Catalog
- **Synced from Scryfall** daily at 2 AM
- **Search by name or code** (case-insensitive)
- **Filter by set type** (expansion, core, masters, etc.)
- **Public API** - no authentication required

---

## Backend Changes

### New Models
| Model | Table | Description |
|-------|-------|-------------|
| `WantListItem` | `want_list_items` | Cards user wants with target prices |
| `Notification` | `notifications` | Unified notification storage |
| `MTGSet` | `mtg_sets` | MTG set metadata from Scryfall |
| `CollectionStats` | `collection_stats` | Cached collection statistics per user |
| `UserMilestone` | `user_milestones` | Achieved collection milestones |

### User Model Extensions
- `email_alerts` (bool) - Enable/disable email notifications
- `price_drop_threshold` (int) - Percentage drop to trigger alerts (default 10%)
- `digest_frequency` (str) - "instant", "daily", or "weekly"

### New API Endpoints

#### Want List (`/api/want-list`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's want list items |
| POST | `/` | Add card to want list |
| GET | `/{id}` | Get single item |
| PATCH | `/{id}` | Update item |
| DELETE | `/{id}` | Remove item |
| POST | `/check-prices` | Find deals (price ≤ target) |

#### Notifications (`/api/notifications`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List notifications (with filters) |
| GET | `/unread-count` | Get unread count by type |
| PATCH | `/{id}` | Mark as read/unread |
| POST | `/mark-all-read` | Mark all as read |
| DELETE | `/{id}` | Delete notification |

#### Collection (`/api/collection`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats` | Get cached collection stats |
| POST | `/stats/refresh` | Force recalculation |
| GET | `/sets` | Get set completion progress |
| GET | `/milestones` | Get achieved milestones |

#### Sets (`/api/sets`) - Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List/search sets |
| GET | `/{code}` | Get set by code |

### New Celery Tasks
| Task | Schedule | Description |
|------|----------|-------------|
| `check_want_list_prices` | Every 15 min | Check prices, create alerts |
| `update_collection_stats` | Hourly at :30 | Update stale stats, check milestones |
| `sync_mtg_sets` | Daily at 2 AM | Sync sets from Scryfall API |

### New Services
- `app/services/notifications.py` - Notification creation with deduplication

---

## Frontend Changes

### Want List Page (`/want-list`)
- Connected to real API (removed mock data)
- Card search autocomplete for adding items
- Priority filtering and sorting
- Real-time price checking with deal detection
- Alert toggle per item

### Notifications
- New `NotificationBell` component in header
- Unread count badge (shows 9+ for >9)
- Dropdown with notification list
- Mark as read/delete actions
- Type-specific icons and priority colors
- Auto-refresh every 30 seconds

### Collection Page (`/collection`)
- Real collection stats from API
- Set completion progress bars with icons
- Milestone achievements display
- Refresh button with loading state
- "Updating..." indicator for stale stats

---

## Database Migration

**File:** `20251228_001_add_collection_wantlist_insights_tables.py`

Creates 5 new tables and adds 3 columns to `users` table. Run with:
```bash
make migrate
```

---

## Testing

### New Test Files
- `tests/api/test_want_list.py` - Want list API tests
- `tests/api/test_notifications.py` - Notification API tests

### Verification
- All Python files compile successfully
- Next.js frontend builds successfully
- Migration syntax validated

---

## Commits (26 total)

### Models (6 commits)
- `fae475b` feat: add WantListItem model for user want lists
- `59b6a1f` feat(models): add Notification model with unified alert types
- `b5a842e` feat(models): add MTGSet model for set collection tracking
- `301c494` feat(models): add CollectionStats model for cached collection metrics
- `5b87654` feat(models): add UserMilestone model for collection achievements
- `7026ced` feat(models): add notification preferences to User model

### Migration (1 commit)
- `b34d0a7` feat(db): add migration for collection, want list, and insights tables

### Schemas (5 commits)
- `1cd2684` feat(schemas): add want list Pydantic schemas
- `6030dda` feat(schemas): add notification Pydantic schemas
- `610ba63` feat(schemas): add collection Pydantic schemas
- `29783fc` feat(schemas): add sets Pydantic schemas
- `02abe69` fix(schemas): address review feedback - add missing fields and exports

### API Routes (4 commits)
- `616614e` feat(api): add want list CRUD endpoints
- `c332980` feat(api): add notification endpoints
- `0f36316` feat(api): add collection stats endpoints
- `85e63c9` feat(api): add sets browsing endpoints

### Services (1 commit)
- `3a6adf8` feat(services): add notification service with deduplication

### Tests (2 commits)
- `c7bd2d8` test(api): add want list endpoint tests
- `916f4e8` test(api): add notification endpoint tests

### Celery Tasks (3 commits)
- `0001b50` feat(tasks): add want list price check task
- `1c46928` feat(tasks): add collection stats update task
- `6aae46c` feat(tasks): add sets sync task from Scryfall

### Frontend (3 commits)
- `eb707be` feat(frontend): connect notifications to backend API
- `cd37827` feat(frontend): connect want list page to backend API
- `8dc8d3f` feat(frontend): connect collection page to backend API

### Documentation (1 commit)
- `a29d364` docs: add Collection, Want List & Insights implementation plan
