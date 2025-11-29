'use client';

import { useParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import Image from 'next/image';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge, ActionBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { LoadingPage } from '@/components/ui/Loading';
import { PriceChart } from '@/components/charts/PriceChart';
import { SpreadChart } from '@/components/charts/SpreadChart';
import { getCard, getCardHistory, refreshCard } from '@/lib/api';
import { formatCurrency, formatPercent, getRarityColor } from '@/lib/utils';

export default function CardDetailPage() {
  const params = useParams();
  const cardId = Number(params.id);

  const [isRefreshing, setIsRefreshing] = useState(false);

  const queryClient = useQueryClient();

  const { data: cardDetail, isLoading, error } = useQuery({
    queryKey: ['card', cardId],
    queryFn: () => getCard(cardId),
    enabled: !!cardId,
  });

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ['card', cardId, 'history'],
    queryFn: () => getCardHistory(cardId, { days: 30 }),
    enabled: !!cardId,
  });

  if (isLoading) return <LoadingPage />;

  if (error || !cardDetail) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">Failed to load card details</p>
        <Link href="/cards">
          <Button variant="secondary">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Search
          </Button>
        </Link>
      </div>
    );
  }

  const { card, metrics, current_prices, recent_signals, active_recommendations, refresh_requested, refresh_reason } = cardDetail;

  const triggerRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      // Use sync=true to get immediate data back
      const updatedData = await refreshCard(cardId, { sync: true });
      // Update the cache with the new data
      queryClient.setQueryData(['card', cardId], updatedData);
      // Also refetch history to get new price points
      await queryClient.invalidateQueries({ queryKey: ['card', cardId, 'history'] });
    } catch (err) {
      console.error('Failed to refresh card', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in">
      {/* Back Button */}
      <Link href="/cards" className="inline-flex items-center text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] transition-colors">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Search
      </Link>

      {/* Card Header */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Card Image */}
        <div className="lg:w-80 shrink-0">
          <div className="aspect-[5/7] relative rounded-xl overflow-hidden bg-[rgb(var(--secondary))] shadow-xl">
            {card.image_url ? (
              <Image
                src={card.image_url}
                alt={card.name}
                fill
                className="object-cover"
                priority
                sizes="320px"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
                No Image
              </div>
            )}
          </div>
        </div>

        {/* Card Info */}
        <div className="flex-1 space-y-6">
          <div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">{card.name}</h1>
                <p className="text-lg text-[rgb(var(--muted-foreground))] mt-1">
                  {card.set_name || card.set_code} #{card.collector_number}
                </p>
              </div>
              {card.rarity && (
                <Badge className={getRarityColor(card.rarity)} size="md">
                  {card.rarity}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3">
              {refresh_requested && (
                <span className="text-sm text-[rgb(var(--muted-foreground))]">
                  Refreshing ({refresh_reason})
                </span>
              )}
              <Button variant="secondary" size="sm" disabled={isRefreshing} onClick={triggerRefresh}>
                {isRefreshing ? 'Refreshing…' : 'Refresh data'}
              </Button>
            </div>

            {card.type_line && (
              <p className="text-[rgb(var(--muted-foreground))] mt-4">{card.type_line}</p>
            )}
            
            {card.mana_cost && (
              <p className="text-[rgb(var(--foreground))] mt-2">
                Mana Cost: {card.mana_cost}
              </p>
            )}

            {card.oracle_text && (
              <p className="text-[rgb(var(--muted-foreground))] mt-4 whitespace-pre-line">
                {card.oracle_text}
              </p>
            )}
          </div>

          {/* Quick Stats */}
          {metrics && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatBox
                label="Avg Price"
                value={formatCurrency(metrics.avg_price)}
              />
              <StatBox
                label="7d Change"
                value={formatPercent(metrics.price_change_7d)}
                valueColor={
                  (metrics.price_change_7d ?? 0) > 0
                    ? 'text-green-500'
                    : (metrics.price_change_7d ?? 0) < 0
                    ? 'text-red-500'
                    : undefined
                }
              />
              <StatBox
                label="Market Spread"
                value={formatPercent(metrics.spread_pct)}
              />
              <StatBox
                label="Listings"
                value={String(metrics.total_listings ?? '-')}
              />
            </div>
          )}
        </div>
      </div>

      {/* Price Comparison */}
      {current_prices.length > 0 && (
        <SpreadChart data={current_prices} title="Current Prices by Marketplace" />
      )}

      {/* Price History */}
      {history && history.history.length > 0 && (
        <PriceChart data={history.history} title="30-Day Price History" />
      )}

      {/* Signals & Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signals */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Signals</CardTitle>
          </CardHeader>
          <CardContent>
            {recent_signals.length > 0 ? (
              <div className="space-y-3">
                {recent_signals.map((signal, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b border-[rgb(var(--border))] last:border-0"
                  >
                    <div>
                      <p className="font-medium text-[rgb(var(--foreground))]">
                        {signal.signal_type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-[rgb(var(--muted-foreground))]">{signal.date}</p>
                    </div>
                    {signal.confidence && (
                      <Badge variant="info">{Math.round(signal.confidence * 100)}%</Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                No recent signals
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle>Active Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            {active_recommendations.length > 0 ? (
              <div className="space-y-4">
                {active_recommendations.map((rec, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-[rgb(var(--secondary))]"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <ActionBadge action={rec.action} />
                      <Badge variant="info">{Math.round(rec.confidence * 100)}% confidence</Badge>
                    </div>
                    <p className="text-sm text-[rgb(var(--muted-foreground))]">{rec.rationale}</p>
                    {rec.potential_profit_pct && (
                      <p className="text-sm mt-2">
                        <span className="text-[rgb(var(--muted-foreground))]">Potential: </span>
                        <span className="text-green-500 font-medium">
                          {formatPercent(rec.potential_profit_pct)}
                        </span>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                No active recommendations
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="p-4 rounded-lg bg-[rgb(var(--secondary))]">
      <p className="text-xs text-[rgb(var(--muted-foreground))]">{label}</p>
      <p className={`text-xl font-bold mt-1 ${valueColor || 'text-[rgb(var(--foreground))]'}`}>
        {value}
      </p>
    </div>
  );
}

