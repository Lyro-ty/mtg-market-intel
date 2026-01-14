'use client';

import { cn, formatRelativeTime } from '@/lib/utils';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { StarRating } from './StarRating';
import type { Review } from '@/types';

interface ReviewCardProps {
  review: Review;
  className?: string;
}

// Trade type badge styling
const tradeTypeBadgeStyles: Record<string, { className: string; label: string }> = {
  buy: {
    className: 'bg-green-500/20 text-green-400 border-green-500/30',
    label: 'Buy',
  },
  sell: {
    className: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    label: 'Sell',
  },
  trade: {
    className: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    label: 'Trade',
  },
  meetup: {
    className: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    label: 'Meetup',
  },
};

/**
 * Get initials from a name (display_name or username)
 */
function getInitials(displayName: string | null, username: string): string {
  const name = displayName || username;
  const parts = name.split(/[\s_-]+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

export function ReviewCard({ review, className }: ReviewCardProps) {
  const { reviewer, rating, comment, trade_type, created_at } = review;
  const displayName = reviewer.display_name || reviewer.username;
  const initials = getInitials(reviewer.display_name, reviewer.username);
  const tradeStyle = trade_type ? tradeTypeBadgeStyles[trade_type.toLowerCase()] : null;

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-700/50 bg-gray-800/50 p-4',
        className
      )}
    >
      {/* Header: Avatar, Name, Stars, Trade Badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <Avatar className="h-10 w-10 flex-shrink-0">
            <AvatarFallback className="bg-gray-700 text-gray-300 text-sm font-medium">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-gray-100 truncate">
                {displayName}
              </span>
              <StarRating rating={rating} size="sm" />
            </div>
            <span className="text-xs text-gray-400">
              {formatRelativeTime(created_at)}
            </span>
          </div>
        </div>
        {tradeStyle && (
          <Badge
            variant="outline"
            className={cn(
              'flex-shrink-0 border',
              tradeStyle.className
            )}
          >
            {tradeStyle.label}
          </Badge>
        )}
      </div>

      {/* Comment */}
      {comment && (
        <p className="mt-3 text-sm text-gray-300 leading-relaxed">
          &ldquo;{comment}&rdquo;
        </p>
      )}
    </div>
  );
}

export default ReviewCard;
