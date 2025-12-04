# Training Data Overview

## Summary
This document lists all training data used for ML models and where it's stored.

---

## 1. Raw Data Sources (PostgreSQL Database)

### 1.1 Cards (`cards` table)
**Location:** PostgreSQL database table `cards`

**Data Fields:**
- `name` - Card name
- `type_line` - Card type (e.g., "Creature — Elf Warrior")
- `oracle_text` - Card text/abilities
- `rarity` - common, uncommon, rare, mythic, special
- `cmc` - Converted mana cost
- `colors` - JSON array of colors (W, U, B, R, G)
- `mana_cost` - Mana cost string
- `set_code` - Set abbreviation
- `collector_number` - Number in set
- `scryfall_id` - Unique Scryfall identifier

**Source:** Scryfall API (via `import_scryfall.py` script)

---

### 1.2 Listings (`listings` table)
**Location:** PostgreSQL database table `listings`

**Data Fields:**
- `price` - Listing price
- `quantity` - Available quantity
- `condition` - NM, LP, MP, HP, DMG
- `language` - English, Japanese, German, etc.
- `is_foil` - Boolean foil flag
- `seller_rating` - Seller rating (0-5)
- `marketplace_id` - Which marketplace (TCGPlayer, Card Kingdom, Cardmarket)
- `card_id` - Foreign key to cards table
- `last_seen_at` - When listing was last observed

**Source:** Web scraping from:
- TCGPlayer (via `TCGPlayerAdapter`)
- Card Kingdom (via `CardKingdomAdapter`)
- Cardmarket (via `CardMarketAdapter`)

**Collection:** 
- Scheduled scraping every 30 minutes (`tasks/ingestion.py`)
- Manual refresh via API (`POST /api/cards/{id}/refresh`)

---

### 1.3 Price Snapshots (`price_snapshots` table)
**Location:** PostgreSQL database table `price_snapshots`

**Data Fields:**
- `price` - Current price
- `price_foil` - Foil price (if available)
- `min_price`, `max_price`, `avg_price`, `median_price` - Market aggregates
- `num_listings` - Number of listings
- `total_quantity` - Total available quantity
- `snapshot_time` - Timestamp
- `card_id` - Foreign key to cards
- `marketplace_id` - Foreign key to marketplaces

**Sources:**
- **Real-time:** Scryfall API (aggregates TCGPlayer, Card Kingdom, Cardmarket prices)
- **Historical:** MTGJSON (weekly price intervals, ~3 months of history)

**Collection:**
- Real-time snapshots: Created during scraping tasks
- Historical snapshots: Imported via `import_mtgjson_historical_prices` task

---

## 2. Processed Training Data (Feature Vectors)

### 2.1 Card Feature Vectors (`card_feature_vectors` table)
**Location:** PostgreSQL database table `card_feature_vectors`

**Storage Format:** Binary (LargeBinary) - numpy array serialized to bytes

**Feature Dimensions:** ~395 dimensions total
- **Text Embedding:** 384 dims (from `all-MiniLM-L6-v2` sentence transformer)
  - Input: Card name + type_line + oracle_text
- **Rarity:** 5 dims (one-hot: common, uncommon, rare, mythic, special)
- **CMC:** 1 dim (normalized: CMC / 10.0, capped at 1.0)
- **Colors:** 5 dims (one-hot: W, U, B, R, G)

**Model Version:** `all-MiniLM-L6-v2` (default)

**Processing:** `services/vectorization/service.py::vectorize_card()`

---

### 2.2 Listing Feature Vectors (`listing_feature_vectors` table)
**Location:** PostgreSQL database table `listing_feature_vectors`

**Storage Format:** Binary (LargeBinary) - numpy array serialized to bytes

**Feature Dimensions:** ~419 dimensions total
- **Card Features:** ~395 dims (from CardFeatureVector)
- **Listing Features:** 24 dims
  - Price: 1 dim (log-normalized: log(1+price)/10)
  - Quantity: 1 dim (normalized: quantity/100, capped at 1.0)
  - Rating: 1 dim (normalized: rating/5.0)
  - Condition: 5 dims (one-hot: NM, LP, MP, HP, DMG)
  - Language: 10 dims (one-hot: English, Japanese, German, French, Italian, Spanish, Portuguese, Korean, Chinese Simplified, Russian)
  - Foil: 1 dim (0.0 or 1.0)
  - Marketplace: 5 dims (one-hot encoded marketplace)

**Model Version:** `all-MiniLM-L6-v2` (default)

**Processing:** `services/vectorization/service.py::vectorize_listing()`

---

## 3. Exported Training Data (Files)

### 3.1 Export Script
**Location:** `backend/app/scripts/export_training_data.py`

**Usage:**
```bash
python -m app.scripts.export_training_data [output_dir] [min_listings_per_card]
```

**Default Output Directory:** `backend/data/training/`

### 3.2 Exported Files
When exported, training data is saved as:

1. **`card_vectors.npy`** - NumPy array of card feature vectors
   - Shape: `(n_samples, 395)`
   - Type: `float32`

2. **`listing_vectors.npy`** - NumPy array of listing feature vectors
   - Shape: `(n_samples, 419)`
   - Type: `float32`

3. **`labels.npy`** - NumPy array of price labels (for supervised learning)
   - Shape: `(n_samples,)`
   - Type: `float32`
   - Values: Listing prices (target variable)

4. **`metadata.json`** - JSON metadata for each sample
   ```json
   {
     "card_id": 123,
     "card_name": "Lightning Bolt",
     "set_code": "M21",
     "listing_id": 456,
     "price": 0.25,
     "condition": "NM",
     "is_foil": false,
     "marketplace_id": 1
   }
   ```

5. **`feature_info.json`** - Feature dimensions and export info
   ```json
   {
     "card_feature_dim": 395,
     "listing_feature_dim": 419,
     "total_samples": 1000,
     "exported_at": "2024-12-03T12:00:00",
     "includes_historical_prices": true,
     "historical_prices": {
       "total_snapshots": 5000,
       "cards_with_history": 250
     }
   }
   ```

6. **`historical_prices.json`** - Historical price data from MTGJSON (if enabled)
   - Format: Array of card price histories
   - Each entry contains card info and array of price snapshots over time
   - Used for time-series analysis and trend prediction

7. **`historical_prices_timeseries.json`** - Time-series format of historical prices
   - Format: `{card_id: {timestamps: [...], prices: [...], prices_foil: [...]}}`
   - Optimized for time-series model training

**Export Criteria:**
- Only cards with feature vectors are included
- Only cards with at least `min_listings_per_card` listings (default: 5)
- Only listings with feature vectors are included

---

## 4. Data Flow

### 4.1 Ingestion Pipeline
```
Scryfall API → Cards Table
     ↓
Web Scraping → Listings Table
     ↓
Price Aggregation → Price Snapshots Table (real-time)
     ↓
MTGJSON Import → Price Snapshots Table (historical)
     ↓
Vectorization Service → Feature Vectors Tables
```

### 4.2 Vectorization Process
1. **Card Vectorization** (when card is created/updated):
   - Extract: name, type_line, oracle_text, rarity, cmc, colors
   - Generate text embedding using SentenceTransformer
   - One-hot encode rarity and colors
   - Normalize CMC
   - Store in `card_feature_vectors` table

2. **Listing Vectorization** (when listing is created/updated):
   - Fetch associated card feature vector
   - Extract: price, quantity, condition, language, is_foil, seller_rating, marketplace_id
   - Normalize numerical features
   - One-hot encode categorical features
   - Concatenate with card vector
   - Store in `listing_feature_vectors` table

### 4.3 Training Data Export
```
Feature Vectors Tables → export_training_data.py → NumPy Files + JSON
Price Snapshots (MTGJSON) → export_training_data.py → historical_prices.json
```

---

## 5. Current Data Status

### 5.1 Database Tables
- ✅ `cards` - Card metadata
- ✅ `listings` - Individual marketplace listings
- ✅ `price_snapshots` - Historical price data
- ✅ `card_feature_vectors` - Pre-computed card vectors
- ✅ `listing_feature_vectors` - Pre-computed listing vectors

### 5.2 Exported Files
- ⚠️ **Not automatically created** - Must run export script manually
- Default location: `backend/data/training/` (currently empty)

### 5.3 Data Collection Status
- **Cards:** Imported from Scryfall (via seed script or import script)
- **Listings:** Scraped from marketplaces (currently low volume - 54 in 24 hours)
- **Price Snapshots (Real-time):** Created during scraping
- **Price Snapshots (Historical):** Imported from MTGJSON via `import_mtgjson_historical_prices` task
- **Feature Vectors:** Generated automatically during ingestion (if vectorization is enabled)

---

## 6. Usage in ML Models

### 6.1 Input Features
- **Card Features:** Card characteristics (text, rarity, colors, CMC)
- **Listing Features:** Listing-specific attributes (price, condition, seller, marketplace)

### 6.2 Target Labels
- **Price Prediction:** Listing price (from `labels.npy`)
- **Recommendation:** Buy/sell/hold signals (derived from price trends)

### 6.3 Model Training
Training data is exported to files for use in external ML training pipelines:
- Price prediction models
- Recommendation engines
- Market trend analysis

---

## 7. Key Files

| File | Purpose |
|------|---------|
| `backend/app/models/card.py` | Card data model |
| `backend/app/models/listing.py` | Listing data model |
| `backend/app/models/price_snapshot.py` | Price snapshot model (real-time + historical) |
| `backend/app/models/feature_vector.py` | Feature vector storage models |
| `backend/app/services/ingestion/adapters/mtgjson.py` | MTGJSON adapter for historical prices |
| `backend/app/services/vectorization/service.py` | Vectorization logic |
| `backend/app/services/vectorization/ingestion.py` | Integration with ingestion pipeline |
| `backend/app/scripts/export_training_data.py` | Export script for training data |
| `backend/app/tasks/ingestion.py` | Scheduled scraping tasks + MTGJSON import |

---

## 8. Notes

- **Embedding Model:** Uses `all-MiniLM-L6-v2` (384-dim embeddings)
- **Storage Format:** Feature vectors stored as binary (numpy arrays) in PostgreSQL
- **Export Format:** NumPy `.npy` files for efficient loading in ML frameworks
- **Data Freshness:** 
  - Listings updated every 30 minutes (scheduled)
  - Historical prices from MTGJSON updated daily/weekly (via scheduled task)
  - Feature vectors updated on ingestion
- **MTGJSON Integration:**
  - Provides historical price data (weekly intervals, ~3 months)
  - Supplements real-time scrapers with price trend data
  - Used for time-series analysis and trend prediction models
  - Data cached locally to reduce API calls
- **Current Limitation:** Low listing count (54 in 24 hours) suggests CSS selectors may need updating

