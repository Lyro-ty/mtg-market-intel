'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Image from 'next/image';
import Link from 'next/link';
import { Filter, TrendingUp, TrendingDown, Minus, Sparkles, Target } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ActionBadge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { PageHeader } from '@/components/ornate/page-header';
import { OrnateCard } from '@/components/ornate/ornate-card';
import { PriceChange } from '@/components/ornate/price-change';
import { getRecommendations } from '@/lib/api';
import { formatCurrency, formatRelativeTime, cn } from '@/lib/utils';
import type { ActionType, Recommendation } from '@/types';

const ACTION_FILTERS: { value: ActionType | 'ALL'; label: string; icon: React.ComponentType<{ className?: string }>; color: string }[] = [
  { value: 'ALL', label: 'All', icon: Filter, color: '' },
  { value: 'BUY', label: 'Buy', icon: TrendingUp, color: 'text-[rgb(var(--success))]' },
  { value: 'SELL', label: 'Sell', icon: TrendingDown, color: 'text-[rgb(var(--destructive))]' },
  { value: 'HOLD', label: 'Hold', icon: Minus, color: 'text-[rgb(var(--warning))]' },
];

// Helper to get rarity based on confidence level
function getConfidenceRarity(confidence: number): 'common' | 'uncommon' | 'rare' | 'mythic' {
  if (confidence >= 0.9) return 'mythic';
  if (confidence >= 0.75) return 'rare';
  if (confidence >= 0.5) return 'uncommon';
  return 'common';
}

// Helper to get glow effect based on action and confidence
function getActionGlow(action: ActionType, confidence: number): string {
  if (confidence < 0.7) return '';

  const glowIntensity = confidence >= 0.85 ? '25px' : '15px';
  const glowOpacity = confidence >= 0.85 ? '0.4' : '0.25';

  switch (action) {
    case 'BUY':
      return `shadow-[0_0_${glowIntensity}_rgb(var(--success)/${glowOpacity})]`;
    case 'SELL':
      return `shadow-[0_0_${glowIntensity}_rgb(var(--destructive)/${glowOpacity})]`;
    case 'HOLD':
      return `shadow-[0_0_${glowIntensity}_rgb(var(--warning)/${glowOpacity})]`;
    default:
      return '';
  }
}

// Summary stat card component
interface SummaryStatProps {
  icon: React.ReactNode;
  count: number;
  label: string;
  colorClass: string;
  bgClass: string;
}

function SummaryStat({ icon, count, label, colorClass, bgClass }: SummaryStatProps) {
  return (
    <OrnateCard rarity="uncommon" hover={false}>
      <div className="text-center py-2">
        <div className={cn('w-10 h-10 mx-auto mb-3 rounded-full flex items-center justify-center', bgClass)}>
          {icon}
        </div>
        <p className={cn('text-3xl font-bold font-heading', colorClass)}>{count}</p>
        <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1">{label}</p>
      </div>
    </OrnateCard>
  );
}

// Recommendation card component
interface RecommendationCardProps {
  recommendation: Recommendation;
}

function ThemedRecommendationCard({ recommendation }: RecommendationCardProps) {
  const rarity = getConfidenceRarity(recommendation.confidence);
  const glowClass = getActionGlow(recommendation.action, recommendation.confidence);

  // Action-based accent colors for hover effects
  const actionAccent = {
    BUY: 'hover:border-[rgb(var(--success))]/50',
    SELL: 'hover:border-[rgb(var(--destructive))]/50',
    HOLD: 'hover:border-[rgb(var(--warning))]/50',
  }[recommendation.action];

  return (
    <OrnateCard
      rarity={rarity}
      className={cn(
        'transition-all duration-300',
        glowClass,
        actionAccent
      )}
    >
      <div className="flex gap-4">
        {/* Card Image */}
        <Link href={`/cards/${recommendation.card_id}`} className="shrink-0">
          <div className="w-20 h-28 relative rounded-lg overflow-hidden bg-[rgb(var(--secondary))] ring-1 ring-[rgb(var(--border))]">
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
                className="font-heading font-semibold text-[rgb(var(--foreground))] hover:text-[rgb(var(--accent))] transition-colors line-clamp-1"
              >
                {recommendation.card_name}
              </Link>
              <p className="text-sm text-[rgb(var(--muted-foreground))] uppercase tracking-wide">
                {recommendation.card_set}
              </p>
            </div>
            <ActionBadge action={recommendation.action} />
          </div>

          {/* Price Info */}
          <div className="flex flex-wrap items-center gap-4 mb-3 text-sm">
            <div>
              <span className="text-[rgb(var(--muted-foreground))]">Current: </span>
              <span className="font-medium text-[rgb(var(--foreground))]">
                {recommendation.current_price ? formatCurrency(recommendation.current_price) : 'N/A'}
              </span>
            </div>
            {recommendation.target_price && (
              <div>
                <span className="text-[rgb(var(--muted-foreground))]">Target: </span>
                <span className="font-medium text-[rgb(var(--magic-gold))]">
                  {formatCurrency(recommendation.target_price)}
                </span>
              </div>
            )}
            {recommendation.potential_profit_pct !== undefined && recommendation.potential_profit_pct !== null && (
              <PriceChange value={recommendation.potential_profit_pct} format="percent" size="md" />
            )}
          </div>

          {/* Rationale */}
          <p className="text-sm text-[rgb(var(--muted-foreground))] line-clamp-2 mb-3 italic">
            &ldquo;{recommendation.rationale}&rdquo;
          </p>

          {/* Footer */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1">
                <Target className="w-3 h-3 text-[rgb(var(--magic-gold))]" />
                <span className="text-[rgb(var(--muted-foreground))]">Confidence:</span>
                <span className={cn(
                  'font-semibold',
                  recommendation.confidence >= 0.8 ? 'text-[rgb(var(--success))]' :
                  recommendation.confidence >= 0.6 ? 'text-[rgb(var(--warning))]' :
                  'text-[rgb(var(--muted-foreground))]'
                )}>
                  {Math.round(recommendation.confidence * 100)}%
                </span>
              </div>
              {recommendation.horizon_days && (
                <div className="text-[rgb(var(--muted-foreground))]">
                  <span>{recommendation.horizon_days}d horizon</span>
                </div>
              )}
            </div>
            <span className="text-[rgb(var(--muted-foreground))]">
              {formatRelativeTime(recommendation.created_at)}
            </span>
          </div>
        </div>
      </div>
    </OrnateCard>
  );
}

export default function RecommendationsPage() {
  const queryClient = useQueryClient();
  const [actionFilter, setActionFilter] = useState<ActionType | 'ALL'>('ALL');
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['recommendations', actionFilter, page],
    queryFn: () =>
      getRecommendations({
        action: actionFilter === 'ALL' ? undefined : actionFilter,
        page,
        pageSize: 20,
      }),
  });

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <PageHeader
        title="Recommendations"
        subtitle="AI-powered trading recommendations based on market analysis"
      >
        <div className="flex items-center gap-2 text-[rgb(var(--magic-gold))]">
          <Sparkles className="w-5 h-5" />
          <span className="text-sm font-medium">Powered by AI</span>
        </div>
      </PageHeader>

      {/* Summary Stats */}
      {data && (
        <div className="grid grid-cols-3 gap-4">
          <SummaryStat
            icon={<TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />}
            count={data.buy_count}
            label="Buy Signals"
            colorClass="text-[rgb(var(--success))]"
            bgClass="bg-[rgb(var(--success))]/20"
          />
          <SummaryStat
            icon={<TrendingDown className="w-5 h-5 text-[rgb(var(--destructive))]" />}
            count={data.sell_count}
            label="Sell Signals"
            colorClass="text-[rgb(var(--destructive))]"
            bgClass="bg-[rgb(var(--destructive))]/20"
          />
          <SummaryStat
            icon={<Minus className="w-5 h-5 text-[rgb(var(--warning))]" />}
            count={data.hold_count}
            label="Hold Signals"
            colorClass="text-[rgb(var(--warning))]"
            bgClass="bg-[rgb(var(--warning))]/20"
          />
        </div>
      )}

      {/* Filters */}
      <Card className="bg-[rgb(var(--card))]/80 backdrop-blur-sm">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-[rgb(var(--muted-foreground))]">Filter by action:</span>
            <div className="flex gap-2">
              {ACTION_FILTERS.map((filter) => {
                const isActive = actionFilter === filter.value;
                return (
                  <Button
                    key={filter.value}
                    variant={isActive ? 'primary' : 'secondary'}
                    size="sm"
                    onClick={() => {
                      setActionFilter(filter.value);
                      setPage(1);
                    }}
                    className={cn(
                      'transition-all',
                      isActive && filter.value === 'BUY' && 'bg-[rgb(var(--success))] hover:bg-[rgb(var(--success))]/90',
                      isActive && filter.value === 'SELL' && 'bg-[rgb(var(--destructive))] hover:bg-[rgb(var(--destructive))]/90',
                      isActive && filter.value === 'HOLD' && 'bg-[rgb(var(--warning))] hover:bg-[rgb(var(--warning))]/90 text-[rgb(var(--background))]',
                      !isActive && filter.color
                    )}
                  >
                    <filter.icon className="w-4 h-4 mr-1.5" />
                    {filter.label}
                  </Button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recommendations List */}
      {isLoading ? (
        <LoadingPage />
      ) : error ? (
        <ErrorDisplay
          message={error instanceof Error ? error.message : 'Failed to load recommendations'}
          status={error instanceof Error && 'status' in error ? (error as Record<string, unknown>).status as number : undefined}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['recommendations', actionFilter, page] })}
        />
      ) : data?.recommendations.length === 0 ? (
        <OrnateCard rarity="uncommon" hover={false}>
          <div className="py-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[rgb(var(--secondary))] flex items-center justify-center">
              <Target className="w-8 h-8 text-[rgb(var(--muted-foreground))]" />
            </div>
            <p className="text-lg font-heading text-[rgb(var(--foreground))] mb-2">
              No recommendations found
            </p>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              {actionFilter === 'ALL'
                ? 'Recommendations are generated periodically based on market analysis.'
                : `No ${actionFilter.toLowerCase()} recommendations at this time.`}
            </p>
          </div>
        </OrnateCard>
      ) : (
        <>
          <div className="text-sm text-[rgb(var(--muted-foreground))] flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[rgb(var(--magic-gold))]" />
            Showing {data?.recommendations.length} of {data?.total} recommendations
          </div>

          <div className="space-y-4">
            {data?.recommendations.map((rec) => (
              <ThemedRecommendationCard key={rec.id} recommendation={rec} />
            ))}
          </div>

          {/* Pagination */}
          {data && data.total > 20 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="min-w-[100px]"
              >
                Previous
              </Button>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-[rgb(var(--muted-foreground))]">Page</span>
                <span className="font-heading font-semibold text-[rgb(var(--foreground))]">{page}</span>
                <span className="text-[rgb(var(--muted-foreground))]">of</span>
                <span className="font-heading font-semibold text-[rgb(var(--foreground))]">{Math.ceil(data.total / 20)}</span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_more}
                className="min-w-[100px]"
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
