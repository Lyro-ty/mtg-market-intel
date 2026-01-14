'use client';

import React, { useState, useCallback } from 'react';
import { Star, StarHalf } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StarRatingProps {
  rating: number; // Current rating (0-5, supports decimals in display mode)
  maxRating?: number; // Default 5
  size?: 'sm' | 'md' | 'lg'; // Size variant
  interactive?: boolean; // Enable click to select
  onRatingChange?: (rating: number) => void; // Callback when rating changes
  showValue?: boolean; // Show numeric value next to stars
  className?: string;
}

const sizeMap = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-6 h-6',
};

const textSizeMap = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
};

export function StarRating({
  rating,
  maxRating = 5,
  size = 'md',
  interactive = false,
  onRatingChange,
  showValue = false,
  className,
}: StarRatingProps) {
  const [hoverRating, setHoverRating] = useState<number | null>(null);

  const displayRating = hoverRating !== null ? hoverRating : rating;

  const handleMouseEnter = useCallback(
    (index: number) => {
      if (interactive) {
        setHoverRating(index + 1);
      }
    },
    [interactive]
  );

  const handleMouseLeave = useCallback(() => {
    if (interactive) {
      setHoverRating(null);
    }
  }, [interactive]);

  const handleClick = useCallback(
    (index: number) => {
      if (interactive && onRatingChange) {
        onRatingChange(index + 1);
      }
    },
    [interactive, onRatingChange]
  );

  const renderStar = (index: number) => {
    const starValue = index + 1;
    const fillAmount = displayRating - index;

    // Determine star state
    const isFull = fillAmount >= 1;
    const isHalf = !isFull && fillAmount >= 0.5;
    const isEmpty = fillAmount < 0.5;

    const iconClasses = cn(
      sizeMap[size],
      'transition-all duration-150',
      interactive && 'cursor-pointer',
      interactive && hoverRating !== null && 'transform hover:scale-110'
    );

    const starContainer = (
      <span
        key={index}
        className={cn('relative inline-block', interactive && 'cursor-pointer')}
        onMouseEnter={() => handleMouseEnter(index)}
        onMouseLeave={handleMouseLeave}
        onClick={() => handleClick(index)}
        role={interactive ? 'button' : undefined}
        aria-label={interactive ? `Rate ${starValue} stars` : undefined}
        tabIndex={interactive ? 0 : undefined}
        onKeyDown={
          interactive
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleClick(index);
                }
              }
            : undefined
        }
      >
        {isHalf ? (
          // Half star - render both empty and half-filled overlay
          <span className="relative inline-block">
            <Star className={cn(iconClasses, 'text-gray-400')} />
            <span className="absolute inset-0 overflow-hidden w-1/2">
              <Star className={cn(iconClasses, 'text-amber-500 fill-amber-500')} />
            </span>
          </span>
        ) : isFull ? (
          // Full star
          <Star className={cn(iconClasses, 'text-amber-500 fill-amber-500')} />
        ) : (
          // Empty star
          <Star className={cn(iconClasses, 'text-gray-400')} />
        )}
      </span>
    );

    return starContainer;
  };

  return (
    <div
      className={cn('inline-flex items-center gap-0.5', className)}
      role={interactive ? 'group' : undefined}
      aria-label={interactive ? 'Star rating selector' : `Rating: ${rating} out of ${maxRating} stars`}
    >
      {Array.from({ length: maxRating }, (_, index) => renderStar(index))}
      {showValue && (
        <span className={cn('ml-1.5 text-gray-300 font-medium', textSizeMap[size])}>
          {rating.toFixed(1)}
        </span>
      )}
    </div>
  );
}

export default StarRating;
