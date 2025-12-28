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
import { getMarketIndex, getTopMovers } from '@/lib/api';
import { formatCurrency, cn } from '@/lib/utils';

// Mock format health data
const mockFormatHealth = [
  { format: 'Standard', health: 'Healthy', change: 2.3, color: 'success' },
  { format: 'Modern', health: 'Hot', change: 5.8, color: 'mythic-orange' },
  { format: 'Legacy', health: 'Stable', change: 0.4, color: 'accent' },
  { format: 'Commander', health: 'Growing', change: 3.1, color: 'success' },
  { format: 'Pioneer', health: 'Cooling', change: -1.2, color: 'warning' },
];

// Mock trending cards
const mockTrendingCards = [
  { name: 'Orcish Bowmasters', set: 'LTR', price: 42.50, change: 15.2, reason: 'Modern staple' },
  { name: 'The One Ring', set: 'LTR', price: 68.00, change: 8.7, reason: 'Multi-format play' },
  { name: 'Ragavan, Nimble Pilferer', set: 'MH2', price: 52.50, change: -5.3, reason: 'Supply increase' },
  { name: 'Sheoldred, the Apocalypse', set: 'DMU', price: 78.00, change: 3.2, reason: 'Standard dominance' },
];

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

function FormatHealthCard({ format }: { format: typeof mockFormatHealth[0] }) {
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

export default function MarketPage() {
  const [indexRange, setIndexRange] = useState<'7d' | '30d' | '90d' | '1y'>('30d');

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
              <span className="text-sm text-muted-foreground">Market Index</span>
            </div>
            <p className="text-2xl font-bold text-foreground">1,247.82</p>
            <PriceChange value={2.4} format="percent" size="sm" />
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-5 h-5 text-[rgb(var(--success))]" />
              <span className="text-sm text-muted-foreground">24h Volume</span>
            </div>
            <p className="text-2xl font-bold text-foreground">$2.4M</p>
            <p className="text-xs text-muted-foreground">+12% vs yesterday</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Flame className="w-5 h-5 text-[rgb(var(--mythic-orange))]" />
              <span className="text-sm text-muted-foreground">Hot Cards</span>
            </div>
            <p className="text-2xl font-bold text-foreground">47</p>
            <p className="text-xs text-muted-foreground">Cards up &gt;10% today</p>
          </CardContent>
        </Card>
        <Card className="glow-accent">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Snowflake className="w-5 h-5 text-[rgb(var(--info))]" />
              <span className="text-sm text-muted-foreground">Cooling Off</span>
            </div>
            <p className="text-2xl font-bold text-foreground">23</p>
            <p className="text-xs text-muted-foreground">Cards down &gt;10% today</p>
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
              {mockFormatHealth.map((format) => (
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
            <div className="space-y-3">
              {mockTrendingCards.map((card, i) => (
                <Link key={i} href={`/cards?search=${encodeURIComponent(card.name)}`}>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 hover:bg-secondary transition-colors">
                    <div>
                      <p className="font-medium text-foreground">{card.name}</p>
                      <p className="text-xs text-muted-foreground">{card.reason}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-foreground">{formatCurrency(card.price)}</p>
                      <PriceChange value={card.change} format="percent" size="sm" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
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
