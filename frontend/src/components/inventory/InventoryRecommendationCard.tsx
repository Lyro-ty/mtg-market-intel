'use client';

import Image from 'next/image';
import Link from 'next/link';
import { AlertTriangle, TrendingDown, Pause, Clock, DollarSign, Store } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { formatCurrency, formatRelativeTime, formatPercent } from '@/lib/utils';
import type { InventoryRecommendation } from '@/types';

interface InventoryRecommendationCardProps {
  recommendation: InventoryRecommendation;
}

const URGENCY_CONFIG = {
  CRITICAL: {
    color: 'bg-red-500/20 text-red-400 border-red-500/50',
    icon: AlertTriangle,
    label: 'CRITICAL',
  },
  HIGH: {
    color: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
    icon: AlertTriangle,
    label: 'HIGH PRIORITY',
  },
  NORMAL: {
    color: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
    icon: Clock,
    label: 'NORMAL',
  },
  LOW: {
    color: 'bg-gray-500/20 text-gray-400 border-gray-500/50',
    icon: Clock,
    label: 'LOW',
  },
};

const ACTION_CONFIG = {
  SELL: {
    color: 'bg-red-500',
    icon: TrendingDown,
    label: 'SELL',
  },
  HOLD: {
    color: 'bg-yellow-500',
    icon: Pause,
    label: 'HOLD',
  },
  BUY: {
    color: 'bg-green-500',
    icon: TrendingDown,
    label: 'BUY',
  },
};

export function InventoryRecommendationCard({ recommendation }: InventoryRecommendationCardProps) {
  const urgencyConfig = URGENCY_CONFIG[recommendation.urgency];
  const actionConfig = ACTION_CONFIG[recommendation.action];
  const UrgencyIcon = urgencyConfig.icon;
  
  return (
    <Card className={`group transition-all border ${urgencyConfig.color}`}>
      <CardContent className="p-0">
        <div className="flex gap-4 p-4">
          {/* Card Image */}
          <Link href={`/cards/${recommendation.card_id}`} className="shrink-0">
            <div className="w-16 h-22 relative rounded-lg overflow-hidden bg-[rgb(var(--secondary))]">
              {recommendation.card_image_url ? (
                <Image
                  src={recommendation.card_image_url}
                  alt={recommendation.card_name}
                  fill
                  className="object-cover"
                  sizes="64px"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-xs text-[rgb(var(--muted-foreground))]">
                  No Img
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
                  className="font-semibold text-[rgb(var(--foreground))] hover:text-amber-500 transition-colors line-clamp-1"
                >
                  {recommendation.card_name}
                </Link>
                <p className="text-sm text-[rgb(var(--muted-foreground))]">
                  {recommendation.card_set}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Urgency Badge */}
                <div className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold ${urgencyConfig.color}`}>
                  <UrgencyIcon className="w-3 h-3" />
                  {urgencyConfig.label}
                </div>
                {/* Action Badge */}
                <div className={`px-2 py-1 rounded-lg text-xs font-bold text-white ${actionConfig.color}`}>
                  {actionConfig.label}
                </div>
              </div>
            </div>
            
            {/* Price Info */}
            <div className="grid grid-cols-3 gap-2 mb-3 text-sm">
              <div>
                <span className="text-[rgb(var(--muted-foreground))]">Current: </span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {formatCurrency(recommendation.current_price)}
                </span>
              </div>
              {recommendation.acquisition_price && (
                <div>
                  <span className="text-[rgb(var(--muted-foreground))]">Paid: </span>
                  <span className="font-medium text-[rgb(var(--foreground))]">
                    {formatCurrency(recommendation.acquisition_price)}
                  </span>
                </div>
              )}
              {recommendation.roi_from_acquisition !== undefined && recommendation.roi_from_acquisition !== null && (
                <div>
                  <span className="text-[rgb(var(--muted-foreground))]">ROI: </span>
                  <span className={`font-bold ${recommendation.roi_from_acquisition >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatPercent(recommendation.roi_from_acquisition, 1)}
                  </span>
                </div>
              )}
            </div>
            
            {/* Rationale */}
            <p className="text-sm text-[rgb(var(--muted-foreground))] line-clamp-2 mb-3">
              {recommendation.rationale}
            </p>
            
            {/* Suggested Action */}
            {(recommendation.suggested_marketplace || recommendation.suggested_listing_price) && (
              <div className="flex items-center gap-3 p-2 rounded-lg bg-[rgb(var(--secondary))]/50 text-sm mb-2">
                {recommendation.suggested_marketplace && (
                  <div className="flex items-center gap-1">
                    <Store className="w-4 h-4 text-[rgb(var(--muted-foreground))]" />
                    <span className="text-[rgb(var(--foreground))]">{recommendation.suggested_marketplace}</span>
                  </div>
                )}
                {recommendation.suggested_listing_price && (
                  <div className="flex items-center gap-1">
                    <DollarSign className="w-4 h-4 text-[rgb(var(--muted-foreground))]" />
                    <span className="text-[rgb(var(--foreground))]">
                      List at {formatCurrency(recommendation.suggested_listing_price)}
                    </span>
                  </div>
                )}
              </div>
            )}
            
            {/* Footer */}
            <div className="flex items-center justify-between text-xs text-[rgb(var(--muted-foreground))]">
              <div className="flex items-center gap-2">
                <span>Confidence:</span>
                <span className="font-medium text-[rgb(var(--foreground))]">
                  {Math.round(recommendation.confidence * 100)}%
                </span>
                <span>•</span>
                <span>{recommendation.horizon_days}d horizon</span>
              </div>
              <span>{formatRelativeTime(recommendation.created_at)}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
