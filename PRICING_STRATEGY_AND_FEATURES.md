# Pricing Strategy & Feature Analysis

## 1. Price Data Separation vs Aggregation for Charting

### The Question: Separate or Aggregate?

**Short Answer**: **Both** - Show separate marketplace lines AND provide aggregated indices. This gives users the best of both worlds.

### Recommended Approach: Hybrid Strategy

#### Option A: Separate Marketplace Charts (Recommended for Detailed Analysis)
**Benefits:**
- ✅ **Currency Clarity**: USD (TCGPlayer) vs EUR (Cardmarket/CardTrader) are clearly separated
- ✅ **Regional Insights**: See market-specific trends (US vs European markets)
- ✅ **Marketplace-Specific Patterns**: Identify when one marketplace moves differently
- ✅ **No Normalization Issues**: Each marketplace chart uses its own currency base
- ✅ **Better for Trading**: Users can see which marketplace offers better prices

**Implementation:**
```python
# Separate indices per marketplace
{
  "marketplace": "tcgplayer",
  "currency": "USD",
  "points": [...],
  "base_value": 100.0
}

{
  "marketplace": "cardtrader",
  "currency": "EUR", 
  "points": [...],
  "base_value": 100.0
}
```

**Use Cases:**
- Detailed price analysis
- Marketplace comparison
- Currency-specific trading decisions
- Identifying arbitrage opportunities

#### Option B: Aggregated Index (Recommended for Overall Market Sentiment)
**Benefits:**
- ✅ **Overall Market View**: Single line showing market direction
- ✅ **Simpler Visualization**: One chart instead of multiple
- ✅ **Better for General Trends**: See if market is generally up/down
- ✅ **Portfolio Valuation**: Better for inventory value tracking

**Requirements for Aggregation:**
1. **Currency Conversion**: Convert all prices to single currency (USD or EUR)
2. **Marketplace Weighting**: Weight by volume/liquidity, not just average
3. **Consistent Normalization**: Use same base point for all marketplaces
4. **Data Quality Weighting**: Weight by data completeness

**Implementation:**
```python
# Aggregated index with proper weighting
{
  "index_type": "aggregated",
  "currency": "USD",  # All converted to USD
  "points": [...],
  "marketplace_weights": {
    "tcgplayer": 0.5,  # 50% weight (high volume)
    "cardtrader": 0.3,  # 30% weight
    "cardmarket": 0.2   # 20% weight
  },
  "base_value": 100.0
}
```

**Use Cases:**
- Overall market sentiment
- Portfolio valuation
- General trend analysis
- Quick market overview

### Recommended Implementation: **Both Approaches**

**Frontend Display:**
1. **Default View**: Aggregated index (simpler, better for most users)
2. **Detailed View**: Toggle to show separate marketplace lines
3. **Comparison Mode**: Side-by-side marketplace comparison

**Backend Strategy:**
```python
# Provide both endpoints
GET /api/market/index?aggregated=true  # Single aggregated index
GET /api/market/index?marketplace=tcgplayer  # Specific marketplace
GET /api/market/index?compare=true  # All marketplaces for comparison
```

**Why This Works:**
- **Aggregated**: Quick overview, portfolio tracking, general trends
- **Separate**: Detailed analysis, marketplace comparison, trading decisions
- **User Choice**: Let users pick what they need

### Charting Best Practice

**For Inventory Charts:**
- Use **aggregated index** (weighted by user's inventory)
- Convert all currencies to user's preferred currency
- Show marketplace breakdown in tooltip/legend

**For Market Analysis:**
- Show **separate marketplace lines** by default
- Allow aggregation toggle
- Include currency conversion in tooltips

## 2. Feature Analysis & Data Availability

### Feature 1: Want List with Market Tracking

**What It Is:**
- Users can create a list of cards they want to buy
- System tracks prices across markets for those cards
- Alerts when prices drop or good deals appear

**How It Helps:**
- ✅ **Price Alerts**: Notify users when cards hit target prices
- ✅ **Market Comparison**: Show best marketplace for each card
- ✅ **Budget Planning**: Track total cost of want list
- ✅ **Timing Optimization**: Identify best time to buy

**Data Availability:**
- ✅ **Scryfall**: Current prices (USD, EUR, TIX)
- ✅ **CardTrader**: Marketplace prices (EUR, multiple listings)
- ✅ **MTGJSON**: Historical prices for trend analysis
- ✅ **Price Snapshots**: Historical data for price alerts

**Implementation Status:**
- ❌ **Not Currently Implemented**
- ✅ **Data Available**: All required price data exists

**Implementation Complexity:** Medium
- Need to create `WantListItem` model
- Add price tracking/alerting system
- Create UI for managing want list

---

### Feature 2: Export Inventory (CSV/Plain Text)

**What It Is:**
- Export user's inventory to CSV or plain text
- Include all relevant data (card name, quantity, condition, value, etc.)

**How It Helps:**
- ✅ **Backup**: Users can backup their inventory
- ✅ **External Analysis**: Use in Excel, Google Sheets, etc.
- ✅ **Sharing**: Share inventory lists with others
- ✅ **Migration**: Move data to other systems

**Data Availability:**
- ✅ **All Inventory Data**: Already stored in database
- ✅ **Card Information**: Linked via card_id
- ✅ **Valuation Data**: current_value, value_change_pct

**Implementation Status:**
- ❌ **Not Currently Implemented**
- ✅ **Data Available**: All required data exists

**Implementation Complexity:** Low
- Simple endpoint to query inventory
- Format as CSV or plain text
- Include all relevant fields

---

### Feature 3: Remove/Update Inventory Items

**What It Is:**
- Users can remove items from inventory
- Users can update quantities, conditions, etc.

**How It Helps:**
- ✅ **Inventory Management**: Keep inventory accurate
- ✅ **Quantity Updates**: Adjust when cards are sold/traded
- ✅ **Condition Updates**: Update condition as cards age
- ✅ **Data Accuracy**: Remove incorrect entries

**Data Availability:**
- ✅ **All Required**: Standard CRUD operations

**Implementation Status:**
- ✅ **Already Implemented!**
  - `DELETE /api/inventory/{item_id}` - Remove items
  - `PATCH /api/inventory/{item_id}` - Update items
- ✅ **Fully Functional**

**Implementation Complexity:** ✅ Complete

---

### Feature 4: Set Detection on Import (3-Letter Code)

**What It Is:**
- When importing cards, detect set from 3-letter code
- Optional: User can specify set or let system detect
- Improves import accuracy

**How It Helps:**
- ✅ **Import Accuracy**: Correctly identify cards by set
- ✅ **Faster Import**: Less manual specification needed
- ✅ **Error Reduction**: Fewer "card not found" errors
- ✅ **Better Matching**: Distinguish between reprints

**Data Availability:**
- ✅ **Set Codes**: Cards have `set_code` field
- ✅ **Set Database**: All sets are in database

**Implementation Status:**
- ⚠️ **Partially Implemented**
  - Basic set detection exists in `parse_plaintext_line()` (line 113)
  - Pattern: `[SET]` or `(SET)` in import text
  - Could be enhanced for better detection

**Current Implementation:**
```python
# Current: Basic pattern matching
set_match = re.search(r'[\(\[]([A-Z0-9]{2,6})[\)\]]', line, re.IGNORECASE)
```

**Enhancement Needed:**
- Better set code validation (check against known sets)
- Fuzzy matching for common set code variations
- Auto-suggest when set code is ambiguous

**Implementation Complexity:** Low-Medium
- Enhance existing parsing logic
- Add set code validation
- Improve error messages

---

### Feature 5: Inventory Search

**What It Is:**
- Search inventory by card name, set, condition, etc.
- Filter and sort results

**How It Helps:**
- ✅ **Find Cards Quickly**: Locate specific cards in large inventory
- ✅ **Filtering**: Find all cards by condition, set, etc.
- ✅ **Organization**: Better inventory management
- ✅ **Analysis**: Find cards matching criteria

**Data Availability:**
- ✅ **All Inventory Data**: Available for search
- ✅ **Card Information**: Linked data available

**Implementation Status:**
- ⚠️ **Partially Implemented**
  - Basic search exists: `GET /api/inventory?search=...` (line 344)
  - Only searches card name currently
  - Could be enhanced with more filters

**Current Implementation:**
```python
# Current: Basic name search only
if search:
    query = query.where(Card.name.ilike(f"%{search}%"))
```

**Enhancement Needed:**
- Search by set code
- Filter by condition
- Filter by foil/non-foil
- Filter by value range
- Sort options

**Implementation Complexity:** Low
- Enhance existing search endpoint
- Add filter parameters
- Add sort options

---

### Feature 6: Foil vs Non-Foil Pricing

**What It Is:**
- Show separate prices for foil and non-foil versions
- Track foil prices in charts and valuations

**How It Helps:**
- ✅ **Accurate Valuations**: Price foil cards correctly
- ✅ **Price Comparison**: See foil premium
- ✅ **Trading Decisions**: Know when foil is worth it
- ✅ **Market Analysis**: Track foil market separately

**Data Availability:**
- ✅ **Foil Prices Available**:
  - Scryfall: `prices.usd_foil`, `prices.eur_foil`
  - CardTrader: Products have `mtg_foil` property
  - MTGJSON: Separate foil prices
  - PriceSnapshot: `price_foil` field exists
- ✅ **Inventory Tracking**: `InventoryItem.is_foil` field exists

**Implementation Status:**
- ⚠️ **Partially Implemented**
  - Foil prices are collected and stored (`price_foil` in PriceSnapshot)
  - Inventory tracks foil status (`is_foil` in InventoryItem)
  - **Missing**: Charts don't separate foil/non-foil
  - **Missing**: Valuations may not use foil prices correctly

**Current Data Structure:**
```python
# PriceSnapshot has foil prices
price_foil: Mapped[Optional[float]]

# InventoryItem tracks foil
is_foil: Mapped[bool]
```

**Enhancement Needed:**
1. **Chart Separation**: Show foil vs non-foil price lines
2. **Valuation Logic**: Use `price_foil` when `is_foil=True`
3. **Price Comparison**: Show foil premium in UI
4. **Market Analysis**: Track foil market trends separately

**Implementation Complexity:** Medium
- Update chart queries to filter by foil
- Update valuation logic
- Add UI for foil/non-foil toggle

---

### Feature 7: Pricing by Condition

**What It Is:**
- Show prices for different card conditions
- Near Mint, Lightly Played, Moderately Played, etc.
- Condition-specific valuations

**How It Helps:**
- ✅ **Accurate Valuations**: Price cards by actual condition
- ✅ **Trading Decisions**: Know condition premium/discount
- ✅ **Market Analysis**: Track condition-specific markets
- ✅ **Inventory Management**: Value cards correctly

**Data Availability:**
- ⚠️ **Partially Available**:
  - **CardTrader**: Products have `condition` property (Near Mint, Slightly Played, etc.)
  - **Scryfall**: May have condition data in some endpoints
  - **MTGJSON**: Limited condition data
  - **PriceSnapshot**: No condition field currently
  - **Listing Model**: Has `condition` field but may not be populated
  - **InventoryItem**: Has `condition` field

**Implementation Status:**
- ⚠️ **Partially Implemented**
  - Inventory tracks condition (`condition` in InventoryItem)
  - Listing model has condition field
  - **Missing**: Price snapshots don't track condition
  - **Missing**: Charts don't separate by condition
  - **Missing**: Condition-specific pricing not implemented

**Current Data Structure:**
```python
# InventoryItem tracks condition
condition: Mapped[str]  # NEAR_MINT, LIGHTLY_PLAYED, etc.

# Listing model has condition
condition: Mapped[Optional[str]]

# PriceSnapshot does NOT have condition
# This is the gap!
```

**Enhancement Needed:**
1. **Add Condition to Price Snapshots**: 
   - Option A: Add `condition` field to PriceSnapshot
   - Option B: Create separate snapshots per condition
2. **Collect Condition Data**: 
   - CardTrader: Already has condition in products
   - Scryfall: May need to check if available
3. **Condition-Specific Charts**: Filter/group by condition
4. **Valuation Logic**: Use condition-appropriate prices

**Implementation Complexity:** Medium-High
- Database migration to add condition to PriceSnapshot
- Update data collection to include condition
- Update chart queries
- Update valuation logic

**Data Source Analysis:**
- ✅ **CardTrader**: Best source - products have explicit condition
- ⚠️ **Scryfall**: May have condition in some data, needs verification
- ❌ **MTGJSON**: Limited condition data

---

## 3. Summary: Data Availability Matrix

| Feature | Data Available | Implementation Status | Complexity |
|---------|---------------|----------------------|------------|
| **Want List** | ✅ Yes | ❌ Not Implemented | Medium |
| **Export Inventory** | ✅ Yes | ❌ Not Implemented | Low |
| **Remove/Update Items** | ✅ Yes | ✅ Implemented | ✅ Complete |
| **Set Detection** | ✅ Yes | ⚠️ Partial | Low-Medium |
| **Inventory Search** | ✅ Yes | ⚠️ Partial (name only) | Low |
| **Foil Pricing** | ✅ Yes | ⚠️ Partial (collected, not used) | Medium |
| **Condition Pricing** | ⚠️ Partial | ⚠️ Partial (tracked, not priced) | Medium-High |

## 4. Recommendations

### High Priority (Easy Wins)
1. **✅ Export Inventory** - Low complexity, high value
2. **✅ Enhanced Inventory Search** - Low complexity, improves UX
3. **✅ Set Detection Enhancement** - Low complexity, improves import accuracy

### Medium Priority (Significant Value)
4. **✅ Foil Pricing Implementation** - Medium complexity, accurate valuations
5. **✅ Want List** - Medium complexity, great user feature

### Lower Priority (Requires More Work)
6. **⚠️ Condition Pricing** - Medium-High complexity, requires data structure changes
   - **Recommendation**: Start with CardTrader data (has condition)
   - Add condition to PriceSnapshot model
   - Implement gradually

### Charting Strategy Recommendation
**Implement Both Approaches:**
- **Default**: Aggregated index (simpler, better for most users)
- **Advanced**: Separate marketplace lines (detailed analysis)
- **Toggle**: Let users choose

This gives flexibility while maintaining simplicity for most users.



