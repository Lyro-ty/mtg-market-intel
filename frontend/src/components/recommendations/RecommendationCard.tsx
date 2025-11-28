'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/Card';
import { ActionBadge, Badge } from '@/components/ui/Badge';
import { formatCurrency, formatPercent, formatRelativeTime } from '@/lib/utils';
import type { Recommendation } from '@/types';

interface RecommendationCardProps {
  recommendation: Recommendation;
}

export function RecommendationCard({ recommendation }: RecommendationCardProps) {

  return (
    <Card className="group hover:border-primary-500/50 transition-all">
      <CardContent className="p-0">
        <div className="flex gap-4 p-4">
          {/* Card Image */}
          <Link href={`/cards/${recommendation.card_id}`} className="shrink-0">
            <div className="w-20 h-28 relative rounded-lg overflow-hidden bg-[rgb(var(--secondary))]">
              {recommendation.card_image_url ? (
                <Image
                  src={recommendation.card_image_url}
                  alt={recommendation.card_name}
                  fill
                  className="object-cover"
                  sizes="80px"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-[rgb(var(--muted-foreground))]">
                  No Image
                </div>
              )}
            </div>
          </Link>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <Link
                  href={`/cards/${recommendation.card_id}`}
                  className="font-semibold text-[rgb(var(--foreground))] hover:text-primary-500 transition-colors line-clamp-1"
                >
                  {recommendation.card_name}
                </Link>
                <p className="text-sm text-[rgb(var(--muted-foreground))]">
                  {recommendation.card_set}
                </p>
              </div>
              <ActionBadge action={recommendation.action} />
            </div>

            {/* Price Info */}
            <div className="flex items-center gap-4 mb-3 text-sm">
              <div>
                <span className="text-[rgb(var(--muted-foreground))]">Current: </span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {formatCurrency(recommendation.current_price)}
                </span>
              </div>
              {recommendation.target_price && (
                <div>
                  <span className="text-[rgb(var(--muted-foreground))]">Target: </span>
                  <span className="font-medium text-[rgb(var(--foreground))]">
                    {formatCurrency(recommendation.target_price)}
                  </span>
                </div>
              )}
              {recommendation.potential_profit_pct && (
                <Badge
                  variant={recommendation.potential_profit_pct > 0 ? 'success' : 'danger'}
                  size="sm"
                >
                  {formatPercent(recommendation.potential_profit_pct)}
                </Badge>
              )}
            </div>

            {/* Rationale */}
            <p className="text-sm text-[rgb(var(--muted-foreground))] line-clamp-2 mb-3">
              {recommendation.rationale}
            </p>

            {/* Footer */}
            <div className="flex items-center justify-between text-xs text-[rgb(var(--muted-foreground))]">
              <div className="flex items-center gap-2">
                <span>Confidence:</span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {Math.round(recommendation.confidence * 100)}%
                </span>
              </div>
              <span>{formatRelativeTime(recommendation.created_at)}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

