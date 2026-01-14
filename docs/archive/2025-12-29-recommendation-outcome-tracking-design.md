# Recommendation Outcome Tracking Design

**Date:** 2025-12-29
**Status:** Draft
**Author:** Claude + User

## Overview

Add automatic outcome tracking to recommendations to measure prediction accuracy. This creates ground truth data for evaluating the current rule-based system and potentially training ML models in the future.

### Goals
- Track what actually happened after each recommendation
- Calculate accuracy scores comparing predicted vs actual price movements
- Display outcomes on recommendation cards in the frontend
- Build a dataset for future ML training

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Feedback type | Automatic (not user ratings) | No friction, objective truth, scales without engagement |
| Success metric | Graded accuracy (0-1) | Captures partial wins, continuous labels for ML |
| HOLD evaluation | Opportunity cost model | HOLD succeeds if no significant move was missed |
| Timing | Track both end price and peak | Distinguishes "signal right but timing off" from "held to target" |
| Storage | Fields on existing table | 1:1 relationship, simpler queries than separate table |
| v1 UI | Per-recommendation outcomes | Immediate visibility, builds trust, analytics can come later |

---

## Database Changes

### New Fields on `recommendations` Table

```python
# Outcome tracking
outcome_evaluated_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True
)
outcome_price_end: Mapped[Optional[float]] = mapped_column(
    Numeric(10, 2), nullable=True
)  # Price at horizon expiry
outcome_price_peak: Mapped[Optional[float]] = mapped_column(
    Numeric(10, 2), nullable=True
)  # Best price during horizon (max for BUY, min for SELL)
outcome_price_peak_at: Mapped[Optional[datetime]] = mapped_column(
    DateTime(timezone=True), nullable=True
)  # When peak was reached

# Accuracy scores (0.0 to 1.0)
accuracy_score_end: Mapped[Optional[float]] = mapped_column(
    Numeric(3, 2), nullable=True
)  # Based on end price vs target
accuracy_score_peak: Mapped[Optional[float]] = mapped_column(
    Numeric(3, 2), nullable=True
)  # Based on peak price vs target

# Actual results for analysis
actual_profit_pct_end: Mapped[Optional[float]] = mapped_column(
    Numeric(10, 2), nullable=True
)  # What you'd have made holding to end
actual_profit_pct_peak: Mapped[Optional[float]] = mapped_column(
    Numeric(10, 2), nullable=True
)  # What you'd have made at optimal exit
```

### Indexes

```python
Index("ix_recommendations_outcome_evaluated", "outcome_evaluated_at"),
Index("ix_recommendations_accuracy", "accuracy_score_end"),
```

---

## Evaluation Logic

### Celery Task

**Task:** `app.tasks.recommendations.evaluate_outcomes`
**Schedule:** Hourly at :30
**Batch size:** 100 recommendations per run

### Query for Unevaluated Recommendations

```sql
SELECT * FROM recommendations
WHERE valid_until < NOW()
  AND outcome_evaluated_at IS NULL
  AND is_active = false  -- Only evaluate after deactivation
ORDER BY valid_until ASC
LIMIT 100;
```

### Accuracy Calculation Algorithm

```python
def evaluate_recommendation(rec: Recommendation, snapshots: list[PriceSnapshot]) -> OutcomeResult:
    """
    Evaluate a recommendation against actual price data.

    Returns None if insufficient data (will retry next run).
    """
    if not snapshots:
        return None

    end_price = snapshots[-1].price
    current = rec.current_price
    target = rec.target_price

    if rec.action == ActionType.BUY:
        peak_price = max(s.price for s in snapshots)
        peak_at = next(s.created_at for s in snapshots if s.price == peak_price)

        predicted_gain = (target - current) / current
        actual_gain_end = (end_price - current) / current
        actual_gain_peak = (peak_price - current) / current

        # Accuracy: 0 if wrong direction, else ratio capped at 1.0
        if actual_gain_end <= 0:
            accuracy_end = 0.0
        else:
            accuracy_end = min(1.0, actual_gain_end / predicted_gain)

        if actual_gain_peak <= 0:
            accuracy_peak = 0.0
        else:
            accuracy_peak = min(1.0, actual_gain_peak / predicted_gain)

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
            profit_pct_end=actual_gain_end * 100,
            profit_pct_peak=actual_gain_peak * 100,
        )

    elif rec.action == ActionType.SELL:
        # For SELL, "peak" is the lowest price (best exit point)
        peak_price = min(s.price for s in snapshots)
        peak_at = next(s.created_at for s in snapshots if s.price == peak_price)

        predicted_drop = (current - target) / current
        actual_drop_end = (current - end_price) / current
        actual_drop_peak = (current - peak_price) / current

        # Accuracy: 0 if price went up, else ratio capped at 1.0
        if actual_drop_end <= 0:
            accuracy_end = 0.0
        else:
            accuracy_end = min(1.0, actual_drop_end / predicted_drop)

        if actual_drop_peak <= 0:
            accuracy_peak = 0.0
        else:
            accuracy_peak = min(1.0, actual_drop_peak / predicted_drop)

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
            profit_pct_end=actual_drop_end * 100,
            profit_pct_peak=actual_drop_peak * 100,
        )

    elif rec.action == ActionType.HOLD:
        # Opportunity cost model: HOLD succeeds if price didn't move >15%
        OPPORTUNITY_THRESHOLD = 0.15

        max_price = max(s.price for s in snapshots)
        min_price = min(s.price for s in snapshots)

        max_up_move = (max_price - current) / current
        max_down_move = (current - min_price) / current
        max_move = max(max_up_move, max_down_move)

        # Accuracy decreases as opportunity cost increases
        accuracy = max(0.0, 1.0 - (max_move / OPPORTUNITY_THRESHOLD))

        # Track the direction of the biggest missed opportunity
        if max_up_move > max_down_move:
            peak_price = max_price
            profit_pct = max_up_move * 100
        else:
            peak_price = min_price
            profit_pct = -max_down_move * 100

        peak_at = next(s.created_at for s in snapshots if s.price == peak_price)

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy,
            accuracy_peak=accuracy,  # Same for HOLD
            profit_pct_end=((end_price - current) / current) * 100,
            profit_pct_peak=profit_pct,
        )
```

### Edge Cases

| Scenario | Handling |
|----------|----------|
| No price snapshots for period | Skip, retry next run |
| Still no data after 24h | Mark `outcome_evaluated_at` with `insufficient_data` flag |
| No target_price (some HOLDs) | Use current_price as baseline |
| Recommendation still active | Don't evaluate until `is_active = false` |
| Price data gaps | Use available snapshots, note in logs |

---

## API Changes

### Schema Updates

```python
# backend/app/schemas/recommendation.py

class RecommendationResponse(RecommendationBase):
    """Full recommendation response."""
    # ... existing fields ...

    # Outcome tracking (new)
    outcome_evaluated_at: Optional[datetime] = None
    outcome_price_end: Optional[float] = None
    outcome_price_peak: Optional[float] = None
    outcome_price_peak_at: Optional[datetime] = None
    accuracy_score_end: Optional[float] = None
    accuracy_score_peak: Optional[float] = None
    actual_profit_pct_end: Optional[float] = None
    actual_profit_pct_peak: Optional[float] = None


class RecommendationFilters(BaseModel):
    """Filters for recommendation queries."""
    # ... existing fields ...

    # Outcome filters (new)
    has_outcome: Optional[bool] = None
    min_accuracy: Optional[float] = Field(None, ge=0, le=1)
    max_accuracy: Optional[float] = Field(None, ge=0, le=1)
```

### Frontend TypeScript Types

```typescript
// frontend/src/types/index.ts

export interface Recommendation {
  // ... existing fields ...

  // Outcome tracking
  outcomeEvaluatedAt: string | null;
  outcomePriceEnd: number | null;
  outcomePricePeak: number | null;
  outcomePricePeakAt: string | null;
  accuracyScoreEnd: number | null;
  accuracyScorePeak: number | null;
  actualProfitPctEnd: number | null;
  actualProfitPctPeak: number | null;
}
```

---

## Frontend Display

### Recommendation Card with Outcome

```
┌─────────────────────────────────────────┐
│ BUY  Force of Negation      Conf: 0.82  │
│ Target: $85  →  Current: $72            │
│ +18% potential                          │
├─────────────────────────────────────────┤
│ OUTCOME (evaluated 2 days ago)          │
│ End: $81 (+12.5%)    Peak: $88 (+22%)   │
│ Accuracy: 69%        Peak Acc: 100% ✓   │
│ ████████░░ Hit target at peak           │
└─────────────────────────────────────────┘
```

### Visual Indicators

| Accuracy | Color | Icon | Label |
|----------|-------|------|-------|
| >= 0.9 | Green | ✓ | "Hit target" |
| 0.5 - 0.9 | Yellow | ~ | "Partially correct" |
| < 0.5 | Red | ✗ | "Missed" |
| null | Gray | ⏳ | "Pending" |

### Outcome Component

```tsx
// frontend/src/components/recommendations/OutcomeDisplay.tsx

interface OutcomeDisplayProps {
  recommendation: Recommendation;
}

export function OutcomeDisplay({ recommendation }: OutcomeDisplayProps) {
  if (!recommendation.outcomeEvaluatedAt) {
    return <Badge variant="secondary">Pending</Badge>;
  }

  const accuracyColor = getAccuracyColor(recommendation.accuracyScoreEnd);
  const peakAccuracyColor = getAccuracyColor(recommendation.accuracyScorePeak);

  return (
    <div className="border-t pt-2 mt-2">
      <div className="text-xs text-muted-foreground mb-1">
        Evaluated {formatRelativeTime(recommendation.outcomeEvaluatedAt)}
      </div>
      <div className="flex justify-between text-sm">
        <span>
          End: ${recommendation.outcomePriceEnd}
          ({formatPercent(recommendation.actualProfitPctEnd)})
        </span>
        <span>
          Peak: ${recommendation.outcomePricePeak}
          ({formatPercent(recommendation.actualProfitPctPeak)})
        </span>
      </div>
      <div className="flex justify-between text-sm mt-1">
        <span className={accuracyColor}>
          Accuracy: {formatPercent(recommendation.accuracyScoreEnd * 100)}
        </span>
        <span className={peakAccuracyColor}>
          Peak: {formatPercent(recommendation.accuracyScorePeak * 100)}
          {recommendation.accuracyScorePeak >= 0.9 && " ✓"}
        </span>
      </div>
    </div>
  );
}
```

---

## Celery Task Registration

```python
# backend/app/tasks/celery_app.py

beat_schedule = {
    # ... existing tasks ...

    "evaluate-recommendation-outcomes": {
        "task": "app.tasks.recommendations.evaluate_outcomes",
        "schedule": crontab(minute=30),  # Every hour at :30
        "options": {"queue": "analytics"},
    },
}
```

---

## Implementation Tasks

1. **Migration** - Add 8 new columns to recommendations table with indexes
2. **Model** - Update Recommendation model with new fields
3. **Schemas** - Update RecommendationResponse and RecommendationFilters
4. **Evaluation service** - Create OutcomeEvaluator class with accuracy algorithms
5. **Celery task** - Create evaluate_outcomes task with batch processing
6. **Task registration** - Add to beat schedule
7. **API route** - Update recommendations endpoint to return outcome fields
8. **Frontend types** - Add outcome fields to Recommendation interface
9. **OutcomeDisplay component** - Create component for showing outcomes
10. **Integration** - Add OutcomeDisplay to recommendation cards

---

## Future Enhancements (Not in v1)

- **User ratings** - Optional thumbs up/down for subjective feedback
- **Dashboard metrics** - Overall accuracy stats, trends over time
- **Analytics page** - Accuracy by signal type, confidence correlation
- **ML training export** - Script to export labeled data for model training
- **A/B testing** - Compare rule-based vs ML recommendations

---

## Success Metrics

After 30 days of data collection, we should be able to answer:
- What is the average accuracy of BUY vs SELL vs HOLD recommendations?
- Do higher confidence recommendations correlate with higher accuracy?
- Which signal types (momentum, spread, trend) produce the most accurate recommendations?
- Is peak accuracy significantly higher than end accuracy? (timing problem)
