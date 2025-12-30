'use client';

import { Badge } from '@/components/ui/badge';
import { formatRelativeTime } from '@/lib/utils';
import type { Recommendation } from '@/types';

interface OutcomeDisplayProps {
  recommendation: Recommendation;
}

/**
 * Get the color class for an accuracy score
 */
function getAccuracyColor(accuracy: number | null | undefined): string {
  if (accuracy === null || accuracy === undefined) {
    return 'text-[rgb(var(--muted-foreground))]';
  }
  if (accuracy >= 0.9) {
    return 'text-green-600';
  }
  if (accuracy >= 0.5) {
    return 'text-yellow-600';
  }
  return 'text-red-500';
}

/**
 * Get the accuracy icon for visual indication
 */
function getAccuracyIcon(accuracy: number | null | undefined): string {
  if (accuracy === null || accuracy === undefined) {
    return '';
  }
  if (accuracy >= 0.9) {
    return ' \u2713'; // checkmark
  }
  if (accuracy >= 0.5) {
    return ' ~';
  }
  return ' \u2717'; // X mark
}

/**
 * Get the accuracy label
 */
function getAccuracyLabel(accuracy: number | null | undefined): string {
  if (accuracy === null || accuracy === undefined) {
    return 'Pending';
  }
  if (accuracy >= 0.9) {
    return 'Hit target';
  }
  if (accuracy >= 0.5) {
    return 'Partially correct';
  }
  return 'Missed';
}

/**
 * Format a percentage value with sign
 */
function formatProfitPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

/**
 * Format a price value
 */
function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `$${value.toFixed(2)}`;
}

/**
 * OutcomeDisplay component shows the evaluation results for a recommendation.
 * Displays the outcome prices, accuracy scores, and whether the recommendation hit its target.
 */
export function OutcomeDisplay({ recommendation }: OutcomeDisplayProps) {
  // If not yet evaluated, show pending badge
  if (!recommendation.outcome_evaluated_at) {
    return (
      <div className="border-t border-[rgb(var(--border))] pt-2 mt-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" size="sm">
            Pending
          </Badge>
          <span className="text-xs text-[rgb(var(--muted-foreground))]">
            Awaiting evaluation
          </span>
        </div>
      </div>
    );
  }

  const accuracyColorEnd = getAccuracyColor(recommendation.accuracy_score_end);
  const accuracyColorPeak = getAccuracyColor(recommendation.accuracy_score_peak);
  const accuracyIconEnd = getAccuracyIcon(recommendation.accuracy_score_end);
  const accuracyIconPeak = getAccuracyIcon(recommendation.accuracy_score_peak);

  return (
    <div className="border-t border-[rgb(var(--border))] pt-2 mt-2 space-y-1">
      {/* Evaluation timestamp */}
      <div className="text-xs text-[rgb(var(--muted-foreground))]">
        Evaluated {formatRelativeTime(recommendation.outcome_evaluated_at)}
      </div>

      {/* Price outcomes */}
      <div className="flex justify-between text-sm">
        <span>
          <span className="text-[rgb(var(--muted-foreground))]">End: </span>
          <span className="font-medium text-[rgb(var(--foreground))]">
            {formatPrice(recommendation.outcome_price_end)}
          </span>
          <span className={recommendation.actual_profit_pct_end && recommendation.actual_profit_pct_end > 0 ? 'text-green-600' : 'text-red-500'}>
            {' '}({formatProfitPercent(recommendation.actual_profit_pct_end)})
          </span>
        </span>
        <span>
          <span className="text-[rgb(var(--muted-foreground))]">Peak: </span>
          <span className="font-medium text-[rgb(var(--foreground))]">
            {formatPrice(recommendation.outcome_price_peak)}
          </span>
          <span className={recommendation.actual_profit_pct_peak && recommendation.actual_profit_pct_peak > 0 ? 'text-green-600' : 'text-red-500'}>
            {' '}({formatProfitPercent(recommendation.actual_profit_pct_peak)})
          </span>
        </span>
      </div>

      {/* Accuracy scores */}
      <div className="flex justify-between text-sm">
        <span className={accuracyColorEnd}>
          Accuracy: {recommendation.accuracy_score_end !== null && recommendation.accuracy_score_end !== undefined
            ? `${(recommendation.accuracy_score_end * 100).toFixed(0)}%`
            : '-'}
          {accuracyIconEnd}
        </span>
        <span className={accuracyColorPeak}>
          Peak: {recommendation.accuracy_score_peak !== null && recommendation.accuracy_score_peak !== undefined
            ? `${(recommendation.accuracy_score_peak * 100).toFixed(0)}%`
            : '-'}
          {accuracyIconPeak}
        </span>
      </div>

      {/* Overall assessment badge */}
      {recommendation.accuracy_score_peak !== null && recommendation.accuracy_score_peak !== undefined && (
        <div className="pt-1">
          <Badge
            variant={recommendation.accuracy_score_peak >= 0.9 ? 'success' : recommendation.accuracy_score_peak >= 0.5 ? 'warning' : 'danger'}
            size="sm"
          >
            {getAccuracyLabel(recommendation.accuracy_score_peak)}
          </Badge>
        </div>
      )}
    </div>
  );
}
