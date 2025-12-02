'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Package, Activity, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { MarketIndexChart } from '@/components/charts/MarketIndexChart';
import { ColorDistributionChart } from '@/components/charts/ColorDistributionChart';
import {
  getMarketOverview,
  getMarketIndex,
  getTopMovers,
  getColorDistribution,
} from '@/lib/api';
import { formatCurrency, formatPercent, formatNumber } from '@/lib/utils';
import type { MarketIndex, VolumeByFormat, ColorDistribution } from '@/types';

export default function DashboardPage() {
  const [marketIndexRange, setMarketIndexRange] = useState<'7d' | '30d' | '90d' | '1y'>('7d');

  // Market Overview Stats
  // Refetch every 2 minutes for real-time data (matches price collection interval)
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['market-overview'],
    queryFn: getMarketOverview,
    refetchInterval: 2 * 60 * 1000, // 2 minutes in milliseconds
    refetchIntervalInBackground: true,
  });

  // Market Index Chart
  // Refetch every 2 minutes for real-time data
  const { data: marketIndex, isLoading: indexLoading } = useQuery({
    queryKey: ['market-index', marketIndexRange],
    queryFn: () => getMarketIndex(marketIndexRange),
    refetchInterval: 2 * 60 * 1000, // 2 minutes in milliseconds
    refetchIntervalInBackground: true,
  });

  // Top Movers (24h)
  // Refetch every 2 minutes for real-time data
  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['top-movers', '24h'],
    queryFn: () => getTopMovers('24h'),
    refetchInterval: 2 * 60 * 1000, // 2 minutes in milliseconds
    refetchIntervalInBackground: true,
  });

  // Color Distribution
  // Refetch every 5 minutes
  const { data: colorDistribution, isLoading: colorLoading } = useQuery({
    queryKey: ['color-distribution', '7d'],
    queryFn: () => getColorDistribution('7d'),
    refetchInterval: 5 * 60 * 1000, // 5 minutes in milliseconds
    refetchIntervalInBackground: true,
  });

  // Progressive loading - show content as it becomes available
  const hasCriticalError = !overview && !overviewLoading;
  
  // Show loading only if we have no data at all
  if (overviewLoading && !overview && !marketIndex && !topMovers && !colorDistribution) {
    return <LoadingPage />;
  }
  
  // Show error state only if critical data fails after loading completes
  if (hasCriticalError) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-2">Failed to load market data</p>
        <p className="text-sm text-[rgb(var(--muted-foreground))]">
          Please try refreshing the page
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Market Dashboard</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          MTG market overview and analytics
        </p>
      </div>

      {/* Market Overview Stats Strip */}
      {overviewLoading && !overview ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="animate-pulse">
                  <div className="h-4 bg-[rgb(var(--secondary))] rounded w-3/4 mb-2"></div>
                  <div className="h-8 bg-[rgb(var(--secondary))] rounded w-1/2 mb-1"></div>
                  <div className="h-3 bg-[rgb(var(--secondary))] rounded w-2/3"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : overview ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Cards Tracked"
            value={formatNumber(overview.totalCardsTracked)}
            subtitle={`${formatNumber(overview.totalListings || 0)} active listings`}
            icon={Package}
          />
          <StatCard
            title="24h Trade Volume"
            value={formatCurrency(overview.volume24hUsd)}
            subtitle="USD trading volume"
            icon={DollarSign}
          />
          <StatCard
            title="24h Avg Price Change"
            value={
              overview.avgPriceChange24hPct !== null
                ? formatPercent(overview.avgPriceChange24hPct)
                : 'N/A'
            }
            subtitle="Across all tracked cards"
            icon={TrendingUp}
            valueColor={
              overview.avgPriceChange24hPct !== null
                ? overview.avgPriceChange24hPct > 0
                  ? 'text-green-500'
                  : overview.avgPriceChange24hPct < 0
                  ? 'text-red-500'
                  : undefined
                : undefined
            }
            badge={
              overview.avgPriceChange24hPct !== null
                ? {
                    value: overview.avgPriceChange24hPct > 0 ? '+' : '',
                    label: formatPercent(overview.avgPriceChange24hPct),
                  }
                : undefined
            }
          />
          <StatCard
            title="Active Formats Tracked"
            value={formatNumber(overview.activeFormatsTracked)}
            subtitle="Different formats"
            icon={Activity}
          />
        </div>
      ) : null}

      {/* Global MTG Market Index */}
      {indexLoading && !marketIndex ? (
        <Card>
          <CardHeader>
            <CardTitle>Market Index</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 animate-pulse bg-[rgb(var(--secondary))] rounded"></div>
          </CardContent>
        </Card>
      ) : marketIndex ? (
        <MarketIndexChart
          data={marketIndex}
          onRangeChange={(range) => setMarketIndexRange(range)}
        />
      ) : null}

      {/* Top Movers: Gainers & Losers */}
      {moversLoading && !topMovers ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardHeader>
                <CardTitle>Loading...</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="h-16 animate-pulse bg-[rgb(var(--secondary))] rounded"></div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : topMovers ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Gainers */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-500" />
                <CardTitle>Top Gainers (24h)</CardTitle>
              </div>
              <Link
                href="/cards?sort=gainers"
                className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1"
              >
                View all <ArrowRight className="w-4 h-4" />
              </Link>
            </CardHeader>
            <CardContent>
              {topMovers.gainers.length > 0 ? (
                <div className="space-y-3">
                  {topMovers.gainers.map((mover, index) => (
                    <MoverItem key={`gainer-${index}`} mover={mover} type="gain" />
                  ))}
                </div>
              ) : (
                <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                  No data available
                </p>
              )}
            </CardContent>
          </Card>

          {/* Top Losers */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-red-500" />
                <CardTitle>Top Losers (24h)</CardTitle>
              </div>
              <Link
                href="/cards?sort=losers"
                className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1"
              >
                View all <ArrowRight className="w-4 h-4" />
              </Link>
            </CardHeader>
            <CardContent>
              {topMovers.losers.length > 0 ? (
                <div className="space-y-3">
                  {topMovers.losers.map((mover, index) => (
                    <MoverItem key={`loser-${index}`} mover={mover} type="loss" />
                  ))}
                </div>
              ) : (
                <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                  No data available
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Color Distribution */}
      {colorLoading && !colorDistribution ? (
        <Card>
          <CardHeader>
            <CardTitle>Color Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 animate-pulse bg-[rgb(var(--secondary))] rounded"></div>
          </CardContent>
        </Card>
      ) : colorDistribution ? (
        <ColorDistributionChart data={colorDistribution} />
      ) : null}
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  valueColor,
  badge,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  valueColor?: string;
  badge?: { value: string; label: string };
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm text-[rgb(var(--muted-foreground))]">{title}</p>
            <div className="flex items-baseline gap-2 mt-1">
              <p className={`text-2xl font-bold ${valueColor || 'text-[rgb(var(--foreground))]'}`}>
                {value}
              </p>
              {badge && (
                <Badge
                  variant={badge.value.startsWith('+') ? 'success' : 'danger'}
                  className="text-xs"
                >
                  {badge.label}
                </Badge>
              )}
            </div>
            <p className="text-xs text-[rgb(var(--muted-foreground))] mt-1">{subtitle}</p>
          </div>
          <div className="p-3 rounded-lg bg-[rgb(var(--secondary))]">
            <Icon className="w-6 h-6 text-[rgb(var(--muted-foreground))]" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MoverItem({
  mover,
  type,
}: {
  mover: {
    cardName: string;
    setCode: string;
    format: string;
    currentPriceUsd: number;
    changePct: number;
    volume: number;
  };
  type: 'gain' | 'loss';
}) {
  return (
    <div className="flex items-center justify-between py-2 hover:bg-[rgb(var(--secondary))]/50 rounded-lg px-2 -mx-2 transition-colors">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <p className="font-medium text-[rgb(var(--foreground))]">{mover.cardName}</p>
          <Badge variant="default" className="text-xs">
            {mover.setCode}
          </Badge>
          <Badge variant="info" className="text-xs">
            {mover.format}
          </Badge>
        </div>
        <p className="text-xs text-[rgb(var(--muted-foreground))] mt-1">
          Volume: {formatNumber(mover.volume)}
        </p>
      </div>
      <div className="text-right">
        <p className="font-medium text-[rgb(var(--foreground))]">
          {formatCurrency(mover.currentPriceUsd)}
        </p>
        <p className={`text-sm font-medium ${type === 'gain' ? 'text-green-500' : 'text-red-500'}`}>
          {formatPercent(mover.changePct)}
        </p>
      </div>
    </div>
  );
}
