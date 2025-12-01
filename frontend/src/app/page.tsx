'use client';

import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Package, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingPage } from '@/components/ui/Loading';
import { CardGrid } from '@/components/cards/CardGrid';
import { getDashboardSummary } from '@/lib/api';
import { formatCurrency, formatPercent, formatNumber } from '@/lib/utils';

export default function DashboardPage() {
  const { data: dashboard, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardSummary,
  });

  if (isLoading) return <LoadingPage />;
  
  if (error) {
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

      {/* Stats Grid */}
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

      {/* Top Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Gainers */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-500" />
              <CardTitle>Top Gainers (7d)</CardTitle>
            </div>
            <Link
              href="/cards?sort=gainers"
              className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>
          <CardContent>
            {dashboard.top_gainers.length > 0 ? (
              <div className="space-y-3">
                {dashboard.top_gainers.map((card) => (
                  <MoverItem key={card.card_id} card={card} type="gain" />
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
              <CardTitle>Top Losers (7d)</CardTitle>
            </div>
            <Link
              href="/cards?sort=losers"
              className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1"
            >
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </CardHeader>
          <CardContent>
            {dashboard.top_losers.length > 0 ? (
              <div className="space-y-3">
                {dashboard.top_losers.map((card) => (
                  <MoverItem key={card.card_id} card={card} type="loss" />
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

