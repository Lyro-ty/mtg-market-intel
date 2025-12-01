'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Package, ArrowRight, BarChart3 } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { CardGrid } from '@/components/cards/CardGrid';
import { MarketIndexChart } from '@/components/charts/MarketIndexChart';
import { VolumeByFormatChart } from '@/components/charts/VolumeByFormatChart';
import { 
  getDashboardSummary, 
  getMarketOverview, 
  getMarketIndex, 
  getTopMovers, 
  getVolumeByFormat 
} from '@/lib/api';
import { formatCurrency, formatPercent, formatNumber } from '@/lib/utils';

export default function DashboardPage() {
  const [marketIndexRange, setMarketIndexRange] = useState<'7d' | '30d' | '90d' | '1y'>('7d');

  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardSummary,
  });

  const { data: marketOverview, isLoading: overviewLoading } = useQuery({
    queryKey: ['market-overview'],
    queryFn: getMarketOverview,
  });

  const { data: marketIndex, isLoading: indexLoading } = useQuery({
    queryKey: ['market-index', marketIndexRange],
    queryFn: () => getMarketIndex(marketIndexRange),
  });

  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['top-movers', '24h'],
    queryFn: () => getTopMovers('24h'),
  });

  const { data: volumeByFormat, isLoading: volumeLoading } = useQuery({
    queryKey: ['volume-by-format', 30],
    queryFn: () => getVolumeByFormat(30),
  });

  const isLoading = dashboardLoading || overviewLoading || indexLoading || moversLoading || volumeLoading;
  
  if (isLoading) return <LoadingPage />;
  
  if (dashboardError) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Failed to load dashboard data</p>
      </div>
    );
  }

  if (!dashboard) return null;

  return (
    <div className="space-y-8 animate-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[rgb(var(--foreground))]">Dashboard</h1>
        <p className="text-[rgb(var(--muted-foreground))] mt-1">
          MTG market overview and recommendations
        </p>
      </div>

      {/* Market Overview Stats Strip */}
      {marketOverview && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MarketStatCard
            title="Total Cards Tracked"
            value={formatNumber(marketOverview.totalCardsTracked)}
            subtitle={marketOverview.totalListings ? `${formatNumber(marketOverview.totalListings)} active listings` : 'Active listings'}
            icon={Package}
          />
          <MarketStatCard
            title="24h Trade Volume"
            value={formatCurrency(marketOverview.volume24hUsd)}
            subtitle="USD"
            icon={DollarSign}
          />
          <MarketStatCard
            title="24h Avg Price Change"
            value={formatPercent(marketOverview.avgPriceChange24hPct)}
            subtitle="Across all tracked cards"
            icon={TrendingUp}
            valueColor={
              (marketOverview.avgPriceChange24hPct ?? 0) > 0
                ? 'text-green-500'
                : (marketOverview.avgPriceChange24hPct ?? 0) < 0
                ? 'text-red-500'
                : undefined
            }
            badge={
              marketOverview.avgPriceChange24hPct !== null
                ? formatPercent(marketOverview.avgPriceChange24hPct)
                : undefined
            }
          />
          <MarketStatCard
            title="Active Formats Tracked"
            value={formatNumber(marketOverview.activeFormatsTracked)}
            subtitle="MTG formats"
            icon={BarChart3}
          />
        </div>
      )}

      {/* Global MTG Market Index Chart */}
      {marketIndex && (
        <MarketIndexChart
          data={marketIndex}
          onRangeChange={setMarketIndexRange}
        />
      )}

      {/* Stats Grid (Legacy - keep for backward compatibility) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Cards"
          value={formatNumber(dashboard.total_cards)}
          subtitle={`${formatNumber(dashboard.total_with_prices)} with prices`}
          icon={Package}
        />
        <StatCard
          title="Avg 7d Change"
          value={formatPercent(dashboard.avg_price_change_7d)}
          subtitle="Across all tracked cards"
          icon={TrendingUp}
          valueColor={
            (dashboard.avg_price_change_7d ?? 0) > 0
              ? 'text-green-500'
              : (dashboard.avg_price_change_7d ?? 0) < 0
              ? 'text-red-500'
              : undefined
          }
        />
        <StatCard
          title="Avg Spread"
          value={formatPercent(dashboard.avg_spread_pct)}
          subtitle="Cross-market spread"
          icon={DollarSign}
        />
        <StatCard
          title="Recommendations"
          value={formatNumber(dashboard.total_recommendations)}
          subtitle={`${dashboard.buy_recommendations} buy, ${dashboard.sell_recommendations} sell`}
          icon={TrendingUp}
        />
      </div>

      {/* Top Movers: Gainers & Losers (24h) */}
      {topMovers && (
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
                  {topMovers.gainers.slice(0, 5).map((mover, index) => (
                    <TopMoverItem key={index} mover={mover} type="gain" />
                  ))}
                </div>
              ) : (
                <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                  {topMovers.isMockData ? 'Showing mock data' : 'No data available'}
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
                  {topMovers.losers.slice(0, 5).map((mover, index) => (
                    <TopMoverItem key={index} mover={mover} type="loss" />
                  ))}
                </div>
              ) : (
                <p className="text-[rgb(var(--muted-foreground))] text-center py-4">
                  {topMovers.isMockData ? 'Showing mock data' : 'No data available'}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Volume by Format Chart */}
      {volumeByFormat && (
        <VolumeByFormatChart data={volumeByFormat} />
      )}

      {/* Arbitrage Opportunities */}
      {dashboard.highest_spreads.length > 0 && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-accent-gold" />
              <CardTitle>Arbitrage Opportunities</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-sm text-[rgb(var(--muted-foreground))]">
                    <th className="pb-3 font-medium">Card</th>
                    <th className="pb-3 font-medium">Lowest</th>
                    <th className="pb-3 font-medium">Highest</th>
                    <th className="pb-3 font-medium text-right">Spread</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgb(var(--border))]">
                  {dashboard.highest_spreads.map((spread) => (
                    <tr key={spread.card_id} className="hover:bg-[rgb(var(--secondary))]/50">
                      <td className="py-3">
                        <Link
                          href={`/cards/${spread.card_id}`}
                          className="font-medium text-[rgb(var(--foreground))] hover:text-primary-500"
                        >
                          {spread.card_name}
                        </Link>
                        <p className="text-xs text-[rgb(var(--muted-foreground))]">
                          {spread.set_code}
                        </p>
                      </td>
                      <td className="py-3">
                        <span className="text-green-500 font-medium">
                          {formatCurrency(spread.lowest_price)}
                        </span>
                        <p className="text-xs text-[rgb(var(--muted-foreground))]">
                          {spread.lowest_marketplace}
                        </p>
                      </td>
                      <td className="py-3">
                        <span className="text-red-500 font-medium">
                          {formatCurrency(spread.highest_price)}
                        </span>
                        <p className="text-xs text-[rgb(var(--muted-foreground))]">
                          {spread.highest_marketplace}
                        </p>
                      </td>
                      <td className="py-3 text-right">
                        <Badge variant="warning">{formatPercent(spread.spread_pct)}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommendations Summary */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recommendation Summary</CardTitle>
          <Link
            href="/recommendations"
            className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1"
          >
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 rounded-lg bg-green-500/10">
              <p className="text-3xl font-bold text-green-500">
                {dashboard.buy_recommendations}
              </p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Buy</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-red-500/10">
              <p className="text-3xl font-bold text-red-500">
                {dashboard.sell_recommendations}
              </p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Sell</p>
            </div>
            <div className="text-center p-4 rounded-lg bg-yellow-500/10">
              <p className="text-3xl font-bold text-yellow-500">
                {dashboard.hold_recommendations}
              </p>
              <p className="text-sm text-[rgb(var(--muted-foreground))]">Hold</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  valueColor,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  valueColor?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">{title}</p>
            <p className={`text-2xl font-bold mt-1 ${valueColor || 'text-[rgb(var(--foreground))]'}`}>
              {value}
            </p>
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

function MarketStatCard({
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
  badge?: string;
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
                <Badge variant={valueColor?.includes('green') ? 'success' : valueColor?.includes('red') ? 'danger' : 'default'}>
                  {badge}
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
  card,
  type,
}: {
  card: { card_id: number; card_name: string; set_code: string; current_price?: number; price_change_pct: number };
  type: 'gain' | 'loss';
}) {
  return (
    <Link
      href={`/cards/${card.card_id}`}
      className="flex items-center justify-between py-2 hover:bg-[rgb(var(--secondary))]/50 rounded-lg px-2 -mx-2 transition-colors"
    >
      <div>
        <p className="font-medium text-[rgb(var(--foreground))]">{card.card_name}</p>
        <p className="text-xs text-[rgb(var(--muted-foreground))]">{card.set_code}</p>
      </div>
      <div className="text-right">
        <p className="font-medium text-[rgb(var(--foreground))]">
          {formatCurrency(card.current_price)}
        </p>
        <p className={type === 'gain' ? 'text-green-500' : 'text-red-500'}>
          {formatPercent(card.price_change_pct)}
        </p>
      </div>
    </Link>
  );
}

function TopMoverItem({
  mover,
  type,
}: {
  mover: { cardName: string; setCode: string; format: string; currentPriceUsd: number; changePct: number; volume: number };
  type: 'gain' | 'loss';
}) {
  return (
    <div className="flex items-center justify-between py-2 hover:bg-[rgb(var(--secondary))]/50 rounded-lg px-2 -mx-2 transition-colors">
      <div className="flex-1">
        <p className="font-medium text-[rgb(var(--foreground))]">{mover.cardName}</p>
        <div className="flex items-center gap-2 mt-1">
          <p className="text-xs text-[rgb(var(--muted-foreground))]">{mover.setCode}</p>
          <Badge variant="default" className="text-xs">
            {mover.format}
          </Badge>
        </div>
      </div>
      <div className="text-right">
        <p className="font-medium text-[rgb(var(--foreground))]">
          {formatCurrency(mover.currentPriceUsd)}
        </p>
        <div className="flex items-center gap-2">
          <p className={type === 'gain' ? 'text-green-500' : 'text-red-500'}>
            {formatPercent(mover.changePct)}
          </p>
          <p className="text-xs text-[rgb(var(--muted-foreground))]">
            {formatNumber(mover.volume)} vol
          </p>
        </div>
      </div>
    </div>
  );
}

