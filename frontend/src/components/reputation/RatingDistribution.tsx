'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { Reputation } from '@/types';

interface RatingDistributionProps {
  reputation: Reputation;
  compact?: boolean; // Smaller version for embedded use
  className?: string;
}

// Star level configuration with colors (5-star to 1-star)
const starLevels = [
  { stars: 5, label: '5', key: 'five_star_count', color: 'bg-emerald-500', barBg: 'bg-emerald-500/20' },
  { stars: 4, label: '4', key: 'four_star_count', color: 'bg-lime-500', barBg: 'bg-lime-500/20' },
  { stars: 3, label: '3', key: 'three_star_count', color: 'bg-yellow-500', barBg: 'bg-yellow-500/20' },
  { stars: 2, label: '2', key: 'two_star_count', color: 'bg-orange-500', barBg: 'bg-orange-500/20' },
  { stars: 1, label: '1', key: 'one_star_count', color: 'bg-red-500', barBg: 'bg-red-500/20' },
] as const;

type StarCountKey = 'five_star_count' | 'four_star_count' | 'three_star_count' | 'two_star_count' | 'one_star_count';

export function RatingDistribution({
  reputation,
  compact = false,
  className,
}: RatingDistributionProps) {
  const { total_reviews } = reputation;

  // Calculate percentage for each star level
  const getPercentage = (count: number): number => {
    if (total_reviews === 0) return 0;
    return (count / total_reviews) * 100;
  };

  // Get count for a star level
  const getCount = (key: StarCountKey): number => {
    return reputation[key];
  };

  return (
    <div
      className={cn(
        'flex flex-col',
        compact ? 'gap-1' : 'gap-2',
        className
      )}
      role="figure"
      aria-label="Rating distribution chart"
    >
      {starLevels.map((level) => {
        const count = getCount(level.key);
        const percentage = getPercentage(count);
        const formattedPercentage = percentage.toFixed(0);

        return (
          <div
            key={level.stars}
            className={cn(
              'flex items-center',
              compact ? 'gap-1.5' : 'gap-2'
            )}
          >
            {/* Star label */}
            <div
              className={cn(
                'flex items-center justify-end flex-shrink-0',
                compact ? 'w-6 text-xs' : 'w-8 text-sm'
              )}
            >
              <span className="text-gray-400 font-medium">{level.label}</span>
              <span className="text-amber-500 ml-0.5">★</span>
            </div>

            {/* Bar container */}
            <div
              className={cn(
                'flex-1 rounded-full overflow-hidden',
                level.barBg,
                compact ? 'h-2' : 'h-3'
              )}
              role="progressbar"
              aria-valuenow={percentage}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${level.stars} star: ${formattedPercentage}%`}
            >
              {/* Filled bar */}
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  level.color
                )}
                style={{ width: `${percentage}%` }}
              />
            </div>

            {/* Percentage and count */}
            <div
              className={cn(
                'flex-shrink-0 text-right',
                compact ? 'w-16 text-xs' : 'w-20 text-sm'
              )}
            >
              <span className="text-gray-300 font-medium">
                {formattedPercentage}%
              </span>
              <span className="text-gray-500 ml-1">
                ({count})
              </span>
            </div>
          </div>
        );
      })}

      {/* Empty state message */}
      {total_reviews === 0 && (
        <p className={cn(
          'text-center text-gray-500 mt-2',
          compact ? 'text-xs' : 'text-sm'
        )}>
          No reviews yet
        </p>
      )}
    </div>
  );
}

export default RatingDistribution;
