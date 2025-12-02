# Bulk Card Vectorization

## Overview

We've added an evening bulk vectorization task that pulls default card data and vectorizes all cards. This significantly improves ML model performance and recommendation speed.

## Benefits

### 1. **Pre-computed Embeddings**
- All cards have feature vectors ready for ML training
- No need to vectorize on-demand during recommendations
- Faster similarity searches and card matching

### 2. **Better ML Training Data**
- Comprehensive feature vectors for all cards
- More consistent data for model training
- Better coverage of the card space

### 3. **Faster Recommendations**
- Similarity searches are instant (no vectorization delay)
- Pre-computed vectors enable faster recommendation generation
- Better user experience with faster response times

### 4. **Automatic Updates**
- New cards are automatically vectorized
- Existing vectors are updated if card data changes
- Ensures data consistency across the system

### 5. **Efficient Processing**
- Batch processing (100 cards per batch)
- Prioritizes cards without vectors first
- Runs during low-traffic hours (11 PM UTC)

## How It Works

### Task: `bulk_vectorize_cards`

**Schedule:** Every evening at 11 PM UTC (via Celery Beat)

**Process:**
1. Gets all cards from database (or specified card IDs)
2. Prioritizes cards without vectors if `prioritize_missing=True`
3. Processes cards in batches of 100
4. Vectorizes each card using the cached VectorizationService
5. Creates new vectors or updates existing ones
6. Commits every 10 batches to avoid long transactions

### Vectorization Details

Each card is vectorized with:
- **Text embeddings**: Card name, type line, oracle text (384-dim from all-MiniLM-L6-v2)
- **Rarity encoding**: One-hot encoded (common, uncommon, rare, mythic, special)
- **Numerical features**: CMC, colors (normalized)
- **Combined vector**: Ready for ML training and similarity search

### Configuration

```python
@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def bulk_vectorize_cards(
    self,
    card_ids: list[int] | None = None,  # None = all cards
    batch_size: int = 100,               # Cards per batch
    prioritize_missing: bool = True,      # Prioritize cards without vectors
) -> dict[str, Any]:
```

## Results

The task returns:
```python
{
    "started_at": "2025-12-02T23:00:00Z",
    "total_cards": 30000,
    "vectors_created": 5000,      # New vectors
    "vectors_updated": 25000,     # Updated vectors
    "vectors_skipped": 0,          # Failed/skipped
    "errors": [],                  # Error details
    "completed_at": "2025-12-03T01:30:00Z"
}
```

## Performance

- **Processing Speed**: ~100 cards per batch
- **Time**: ~2-3 hours for ~30k cards (default_cards)
- **Memory**: Efficient batch processing
- **Database**: Commits every 10 batches to avoid long transactions

## Monitoring

Check logs for progress:
```bash
docker logs dualcaster-worker | grep -i "vectorization"
```

Look for:
- `Starting bulk card vectorization`
- `Vectorization progress` (every 10 batches)
- `Bulk vectorization complete`

## Manual Execution

You can also run it manually:
```python
from app.tasks.ingestion import bulk_vectorize_cards

# Vectorize all cards
result = bulk_vectorize_cards.delay()

# Vectorize specific cards
result = bulk_vectorize_cards.delay(card_ids=[1, 2, 3])

# Vectorize with custom batch size
result = bulk_vectorize_cards.delay(batch_size=50)
```

## Integration with Existing System

- **Refresh endpoint**: Still vectorizes cards on-demand (for immediate use)
- **Bulk task**: Ensures all cards are vectorized (for comprehensive coverage)
- **No conflicts**: Both can run simultaneously, updates are idempotent

## Future Improvements

Potential enhancements:
1. **Incremental updates**: Only vectorize cards that changed
2. **Parallel processing**: Use multiple workers for faster processing
3. **Smart prioritization**: Prioritize inventory cards or frequently accessed cards
4. **Vector versioning**: Track model version changes and re-vectorize when needed

## Related Files

- `backend/app/tasks/ingestion.py` - Task implementation
- `backend/app/tasks/celery_app.py` - Celery Beat schedule
- `backend/app/services/vectorization/` - Vectorization service
- `backend/app/models/feature_vector.py` - CardFeatureVector model

