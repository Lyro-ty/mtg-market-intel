# News API & Frontend Design

**Date:** 2025-12-31
**Status:** Approved
**Author:** Claude + User

## Overview

Add news API endpoints and frontend pages to display MTG news articles collected from RSS feeds and NewsAPI.ai. News appears in three places: dedicated /news page, dashboard widget, and card detail pages.

## API Endpoints

### GET /api/news
List articles with pagination, newest first.

**Query params:**
- `source` (optional): Filter by source name
- `limit` (default 20, max 100)
- `offset` (default 0)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Our 25 favorite MTG cards...",
      "source": "newsapi:Polygon",
      "source_display": "Polygon",
      "published_at": "2024-12-30T12:00:00Z",
      "external_url": "https://...",
      "summary": "First 200 chars...",
      "card_mention_count": 3
    }
  ],
  "total": 40,
  "has_more": true
}
```

### GET /api/news/{id}
Single article with card mentions.

**Response:**
```json
{
  "id": 1,
  "title": "...",
  "source": "newsapi:Polygon",
  "source_display": "Polygon",
  "published_at": "...",
  "external_url": "...",
  "summary": "...",
  "author": "John Doe",
  "card_mentions": [
    {
      "card_id": 123,
      "card_name": "Black Lotus",
      "context": "...Black Lotus sees play in..."
    }
  ]
}
```

### GET /api/cards/{id}/news
News mentioning a specific card.

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "...",
      "source_display": "Polygon",
      "published_at": "...",
      "external_url": "...",
      "context": "...this card sees play in..."
    }
  ],
  "total": 5
}
```

## Frontend Components

### News Page (`/news`)
- PageHeader with "News" title
- Source filter dropdown
- Vertical list of NewsArticleCard components
- Load more button for pagination

### Dashboard Widget
- "Latest News" card showing 5 recent articles
- Compact format: source, title, time ago
- "View All" link to /news

### Card Detail Section
- "In the News" section on card pages
- Shows up to 5 articles mentioning the card
- Displays context snippet

### NewsArticleCard Component
Reusable card showing:
- Source badge (with icon for known sources)
- Title (external link)
- Published time (relative)
- Summary snippet
- Card mention count badge

## Files to Create/Modify

**Backend:**
- `backend/app/api/routes/news.py` (new)
- `backend/app/schemas/news.py` (new)
- `backend/app/api/routes/cards.py` (add endpoint)
- `backend/app/api/routes/__init__.py` (register router)

**Frontend:**
- `frontend/src/lib/api.ts` (add functions)
- `frontend/src/types/index.ts` (add types)
- `frontend/src/app/(protected)/news/page.tsx` (new)
- `frontend/src/components/news/NewsArticleCard.tsx` (new)
- `frontend/src/app/(protected)/dashboard/page.tsx` (add widget)
- `frontend/src/app/(public)/cards/[id]/page.tsx` (add section)

## Implementation Tasks

1. Create backend schemas (news.py)
2. Create news API routes (news.py)
3. Add card news endpoint to cards.py
4. Register news router
5. Add frontend types and API functions
6. Create NewsArticleCard component
7. Create /news page
8. Add dashboard widget
9. Add card detail news section
