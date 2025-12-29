'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity,
  Flame,
  Snowflake,
  ArrowRight,
  Clock,
  DollarSign,
  Percent,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/ornate/page-header';
import { PriceChange } from '@/components/ornate/price-change';
import { MarketIndexChart } from '@/components/charts/MarketIndexChart';
import { getMarketIndex, getTopMovers, getMarketOverview } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';

// Format health data - placeholder until API endpoint is implemented
const formatHealthData = [
  { format: 'Standard', health: 'Healthy', change: 2.3, color: 'success' },
  { format: 'Modern', health: 'Hot', change: 5.8, color: 'mythic-orange' },
  { format: 'Legacy', health: 'Stable', change: 0.4, color: 'accent' },
  { format: 'Commander', health: 'Growing', change: 3.1, color: 'success' },
  { format: 'Pioneer', health: 'Cooling', change: -1.2, color: 'warning' },
];

function FormatHealthCard({ format }: { format: typeof formatHealthData[0] }) {
  const colorMap: Record<string, string> = {
    success: 'text-[rgb(var(--success))]',
    'mythic-orange': 'text-[rgb(var(--mythic-orange))]',
    accent: 'text-[rgb(var(--accent))]',
    warning: 'text-[rgb(var(--warning))]',
  };

  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50">
      <div className="flex items-center gap-3">
        <Activity className={cn('w-5 h-5', colorMap[format.color])} />
        <div>
          <p className="font-medium text-foreground">{format.format}</p>
          <p className={cn('text-sm', colorMap[format.color])}>{format.health}</p>
        </div>
      </div>
      <PriceChange value={format.change} format="percent" size="sm" />
    </div>
  );
}


function MoverCard({
  card,
  type
}: {
  card: { cardName: string; setCode: string; currentPriceUsd: number; changePct: number };
  type: 'gainer' | 'loser';
}) {
  return (
    <Link href={`/cards?search=${encodeURIComponent(card.cardName)}`}>
      <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors cursor-pointer">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground truncate">{card.cardName}</p>
          <p className="text-xs text-muted-foreground uppercase">{card.setCode}</p>
        </div>
        <div className="text-right ml-4">
          <p className="font-medium text-foreground">{formatCurrency(card.currentPriceUsd)}</p>
          <PriceChange value={card.changePct} format="percent" size="sm" />
        </div>
      </div>
    </Link>
  );
}


export default function MarketPage() {
  const [indexRange, setIndexRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');

  // Fetch market overview stats
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['market-overview'],
    queryFn: getMarketOverview,
    refetchInterval: 5 * 60 * 1000,
  });

  // Fetch market index
  const { data: marketIndex, isLoading: indexLoading } = useQuery({
    queryKey: ['market-index', indexRange],
    queryFn: () => getMarketIndex(indexRange),
    refetchInterval: 5 * 60 * 1000,
  });

  // Fetch top movers
  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['top-movers', '24h'],
    queryFn: () => getTopMovers('24h'),
    refetchInterval: 5 * 60 * 1000,
  });

  // Calculate hot/cooling cards from top movers
  const hotCardsCount = topMovers?.gainers?.filter(c => c.changePct > 10).length ?? 0;
  const coolingCardsCount = topMovers?.losers?.filter(c => c.changePct < -10).length ?? 0;

  // Format volume for display
  const formatVolume = (volume: number) => {
    if (volume >= 1000000) return `$${(volume / 1000000).toFixed(1)}M`;
    if (volume >= 1000) return `$${(volume / 1000).toFixed(0)}K`;
    return `$${volume.toFixed(0)}`;
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-8">
      <PageHeader
        title="Market Overview"
        subtitle="Real-time MTG market intelligence and price trends"
      />

      {/* Market Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
              <span className="text-sm text-muted-foreground">Cards Tracked</span>
            </div>
            {overviewLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <>
                <p className="text-2xl font-bold text-foreground">
                  {overview?.totalCardsTracked?.toLocaleString() ?? '-'}
                </p>
                <p className="text-xs text-muted-foreground">Total cards in database</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-5 h-5 text-[rgb(var(--success))]" />
              <span className="text-sm text-muted-foreground">24h Volume</span>
            </div>
            {overviewLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <>
                <p className="text-2xl font-bold text-foreground">
                  {overview?.volume24hUsd ? formatVolume(overview.volume24hUsd) : '-'}
                </p>
                {overview?.avgPriceChange24hPct !== null && overview?.avgPriceChange24hPct !== undefined && (
                  <PriceChange value={overview.avgPriceChange24hPct} format="percent" size="sm" />
                )}
              </>
            )}
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Flame className="w-5 h-5 text-[rgb(var(--mythic-orange))]" />
              <span className="text-sm text-muted-foreground">Hot Cards</span>
            </div>
            {moversLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <p className="text-2xl font-bold text-foreground">{hotCardsCount}</p>
                <p className="text-xs text-muted-foreground">Cards up &gt;10% today</p>
              </>
            )}
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Snowflake className="w-5 h-5 text-[rgb(var(--info))]" />
              <span className="text-sm text-muted-foreground">Cooling Off</span>
            </div>
            {moversLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <>
                <p className="text-2xl font-bold text-foreground">{coolingCardsCount}</p>
                <p className="text-xs text-muted-foreground">Cards down &gt;10% today</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Market Index Chart */}
      <Card className="glow-accent">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
              Market Index
            </CardTitle>
            <div className="flex gap-1">
              {(['7d', '30d', '90d', '1y'] as const).map((range) => (
                <Button
                  key={range}
                  variant={indexRange === range ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setIndexRange(range)}
                  className={indexRange === range ? 'gradient-arcane text-white' : ''}
                >
                  {range}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {indexLoading && !marketIndex ? (
            <Skeleton className="h-64 w-full" />
          ) : marketIndex ? (
            <MarketIndexChart
              data={marketIndex}
              title=""
              onRangeChange={setIndexRange}
            />
          ) : (
            <div className="h-64 flex items-center justify-center border border-dashed border-border rounded-lg">
              <p className="text-muted-foreground">Market data loading...</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gainers & Losers */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="glow-accent">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-[rgb(var(--success))]" />
                Top Gainers (24h)
              </CardTitle>
              <Link href="/cards?sort=change_desc" className="text-sm text-[rgb(var(--accent))] hover:underline flex items-center gap-1">
                View all <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {moversLoading && !topMovers ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : topMovers?.gainers && topMovers.gainers.length > 0 ? (
              <div className="space-y-2">
                {topMovers.gainers.slice(0, 5).map((card, i) => (
                  <MoverCard key={i} card={card} type="gainer" />
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">No gainers data available</p>
            )}
          </CardContent>
        </Card>

        <Card className="glow-accent">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-[rgb(var(--destructive))]" />
                Top Losers (24h)
              </CardTitle>
              <Link href="/cards?sort=change_asc" className="text-sm text-[rgb(var(--accent))] hover:underline flex items-center gap-1">
                View all <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {moversLoading && !topMovers ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : topMovers?.losers && topMovers.losers.length > 0 ? (
              <div className="space-y-2">
                {topMovers.losers.slice(0, 5).map((card, i) => (
                  <MoverCard key={i} card={card} type="loser" />
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">No losers data available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Format Health & Trending */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Format Health */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[rgb(var(--accent))]" />
              Format Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {formatHealthData.map((format) => (
                <FormatHealthCard key={format.format} format={format} />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Trending Cards */}
        <Card className="glow-accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Flame className="w-5 h-5 text-[rgb(var(--mythic-orange))]" />
              Trending Now
            </CardTitle>
          </CardHeader>
          <CardContent>
            {moversLoading && !topMovers ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : topMovers?.gainers && topMovers.gainers.length > 0 ? (
              <div className="space-y-3">
                {topMovers.gainers.slice(0, 4).map((card, i) => (
                  <Link key={i} href={`/cards?q=${encodeURIComponent(card.cardName)}`}>
                    <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-foreground truncate">{card.cardName}</p>
                        <p className="text-xs text-muted-foreground uppercase">{card.setCode}</p>
                      </div>
                      <div className="text-right ml-4">
                        <p className="font-medium text-foreground">{formatCurrency(card.currentPriceUsd)}</p>
                        <PriceChange value={card.changePct} format="percent" size="sm" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-8">No trending data available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Last Updated */}
      <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
        <Clock className="w-4 h-4" />
        <span>Market data updates every 5 minutes</span>
      </div>
    </div>
  );
}
