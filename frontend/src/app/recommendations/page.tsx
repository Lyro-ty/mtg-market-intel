'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Filter, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { RecommendationCard } from '@/components/recommendations/RecommendationCard';
import { useQueryClient } from '@tanstack/react-query';
import { getRecommendations } from '@/lib/api';
import type { ActionType } from '@/types';

const ACTION_FILTERS: { value: ActionType | 'ALL'; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: 'ALL', label: 'All', icon: Filter },
  { value: 'BUY', label: 'Buy', icon: TrendingUp },
  { value: 'SELL', label: 'Sell', icon: TrendingDown },
  { value: 'HOLD', label: 'Hold', icon: Minus },
];

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
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Recommendations</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          AI-powered trading recommendations based on market analysis
        </p>
      </div>

      {/* Summary Stats */}
      {data && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <TrendingUp className="w-8 h-8 mx-auto text-green-500 mb-2" />
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">{data.buy_count}</p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Buy Signals</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <TrendingDown className="w-8 h-8 mx-auto text-red-500 mb-2" />
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">{data.sell_count}</p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Sell Signals</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <Minus className="w-8 h-8 mx-auto text-yellow-500 mb-2" />
              <p className="text-2xl font-bold text-[rgb(var(--foreground))]">{data.hold_count}</p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Hold Signals</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-[rgb(var(--muted-foreground))]">Filter by action:</span>
            <div className="flex gap-2">
              {ACTION_FILTERS.map((filter) => (
                <Button
                  key={filter.value}
                  variant={actionFilter === filter.value ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => {
                    setActionFilter(filter.value);
                    setPage(1);
                  }}
                >
                  <filter.icon className="w-4 h-4 mr-1" />
                  {filter.label}
                </Button>
              ))}
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
          status={error instanceof Error && 'status' in error ? (error as any).status : undefined}
          onRetry={() => queryClient.invalidateQueries({ queryKey: ['recommendations', actionFilter, page] })}
        />
      ) : data?.recommendations.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-[rgb(var(--muted-foreground))]">
              No recommendations found
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-[rgb(var(--muted-foreground))]">
            Showing {data?.recommendations.length} of {data?.total} recommendations
          </div>

          <div className="space-y-4">
            {data?.recommendations.map((rec) => (
              <RecommendationCard key={rec.id} recommendation={rec} />
            ))}
          </div>

          {/* Pagination */}
          {data && data.total > 20 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-[rgb(var(--muted-foreground))]">
                Page {page} of {Math.ceil(data.total / 20)}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_more}
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

