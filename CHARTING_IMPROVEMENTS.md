# Charting Improvements - Live Data & Freshness Indicators

## Overview
Enhanced all price charts and dashboards to show data freshness, collection intervals, and provide live auto-refresh functionality.

## Key Improvements

### 1. Price Chart Enhancements (`PriceChart.tsx`)

**New Features:**
- **Data Freshness Indicator**: Shows how old the data is with color-coded status
  - 🟢 Green: < 1 hour (Live/Fresh)
  - 🟡 Amber: 1-24 hours (Stale)
  - 🔴 Red: > 24 hours (Very Stale)
- **Timestamp Display**: Shows exact collection time in tooltips
- **Data Age in Tooltips**: Each data point shows minutes since collection
- **Auto-refresh Support**: Component accepts refresh props for live updates

**Visual Indicators:**
- Pulsing dot indicator showing data freshness
- Relative time display (e.g., "5m ago", "2h ago")
- Full timestamp in tooltip on hover

### 2. Spread Chart Enhancements (`SpreadChart.tsx`)

**New Features:**
- **Last Updated Display**: Shows when each marketplace price was last updated
- **Freshness Indicator**: Color-coded status for data freshness
- **Tooltip Enhancements**: Shows update time for each marketplace

### 3. Auto-Refresh System

**Card Detail Page:**
- Auto-refreshes every **60 seconds** (configurable)
- Continues refreshing even when tab is in background
- Updates both card data and price history
- Seamless updates without page reload

**Configuration:**
```typescript
refetchInterval: 60000,  // 60 seconds
refetchIntervalInBackground: true
```

### 4. API Enhancements

**Price History Endpoint (`/cards/{id}/history`):**
- Added `snapshot_time` to each `PricePoint`
- Added `data_age_minutes` to each `PricePoint`
- Added `latest_snapshot_time` to response
- Added `data_freshness_minutes` to response

**Current Prices Endpoint (`/cards/{id}/prices`):**
- Already includes `last_updated` timestamp per marketplace
- Used by SpreadChart for freshness display

### 5. Type Updates

**Frontend Types (`types/index.ts`):**
- `PricePoint`: Added `snapshot_time` and `data_age_minutes`
- `CardHistory`: Added `latest_snapshot_time` and `data_freshness_minutes`

**Backend Schemas (`schemas/card.py`):**
- `PricePoint`: Added optional `snapshot_time` and `data_age_minutes`
- `CardHistoryResponse`: Added `latest_snapshot_time` and `data_freshness_minutes`

## Data Collection Intervals

### Scheduled Tasks
- **All Cards**: Every 5 minutes (`collect_price_data`)
- **Inventory Cards**: Every 2 minutes (`collect_inventory_prices`)
- **Historical Data**: Daily at 3 AM (`import_mtgjson_historical_prices`)

### Frontend Refresh
- **Card Detail Page**: Every 60 seconds (auto-refresh)
- **Price Charts**: Show real-time freshness status
- **Manual Refresh**: Available via refresh button

## User Experience

### Visual Feedback
1. **Live Indicator**: Green pulsing dot when data is fresh (< 1 hour)
2. **Stale Warning**: Amber indicator when data is 1-24 hours old
3. **Very Stale Alert**: Red indicator when data is > 24 hours old
4. **Tooltip Details**: Hover over data points to see exact collection time

### Automatic Updates
- Charts update automatically every 60 seconds
- No page reload required
- Smooth transitions with React Query cache updates

## Technical Implementation

### Backend Changes
- `backend/app/api/routes/cards.py`: Enhanced history endpoint with freshness data
- `backend/app/schemas/card.py`: Added timestamp fields to schemas

### Frontend Changes
- `frontend/src/components/charts/PriceChart.tsx`: Added freshness indicators
- `frontend/src/components/charts/SpreadChart.tsx`: Added update time display
- `frontend/src/app/cards/[id]/page.tsx`: Added auto-refresh
- `frontend/src/types/index.ts`: Updated type definitions

## Benefits

1. **Transparency**: Users can see exactly when data was collected
2. **Trust**: Clear indication of data freshness builds confidence
3. **Real-time Feel**: Auto-refresh makes data feel live and current
4. **Decision Making**: Users know if data is recent enough for trading decisions
5. **Staleness Detection**: Visual warnings when data is too old

## Future Enhancements

Potential improvements:
- WebSocket support for real-time push updates
- Configurable refresh intervals per user
- Notification when data becomes stale
- Historical freshness trends
- Data quality scores based on collection frequency

