'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  TrendingUp,
  TrendingDown,
  Bell,
  BarChart3,
  Package,
  ArrowRight,
  Sparkles,
  DollarSign,
  Target,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Skeleton,
  StatsSkeleton,
  ChartSkeleton,
  CardSkeleton,
} from '@/components/ui/skeleton';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { getInventoryAnalytics, getInventoryTopMovers, getRecommendations } from '@/lib/api';
import { formatCurrency, formatPercent, cn } from '@/lib/utils';

// StatCard helper component
interface StatCardProps {
  title: string;
  value: string;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon?: React.ReactNode;
  className?: string;
}

function StatCard({ title, value, change, trend, icon, className }: StatCardProps) {
  const trendColor =
    trend === 'up'
      ? 'text-green-500'
      : trend === 'down'
        ? 'text-red-500'
        : 'text-[rgb(var(--muted-foreground))]';

  const TrendIcon =
    trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : null;

  return (
    <Card className={cn('', className)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-[rgb(var(--muted-foreground))]">{title}</span>
          {icon && <div className="text-[rgb(var(--accent))]">{icon}</div>}
        </div>
        <p className="text-2xl font-bold text-[rgb(var(--foreground))]">{value}</p>
        {change && (
          <div className={cn('flex items-center gap-1 text-sm mt-1', trendColor)}>
            {TrendIcon && <TrendIcon className="w-4 h-4" />}
            <span>{change}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// DashboardSkeleton for loading state
function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-in">
      {/* Greeting skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>

      {/* Stats row skeleton */}
      <StatsSkeleton />

      {/* Main content grid skeleton */}
      <div className="grid md:grid-cols-2 gap-6">
        <ChartSkeleton />
        <CardSkeleton />
      </div>

      {/* Recommendations skeleton */}
      <CardSkeleton />
    </div>
  );
}

// EmptyDashboard for new users with no data
function EmptyDashboard({ username }: { username: string }) {
  return (
    <div className="space-y-6 animate-in">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-bold text-[rgb(var(--foreground))]">
          Welcome, {username}!
        </h1>
        <p className="text-[rgb(var(--muted-foreground))]">
          Let&apos;s get started with your MTG collection
        </p>
      </div>

      {/* Empty state card */}
      <Card className="bg-gradient-to-br from-[rgba(var(--accent),0.1)] to-[rgba(var(--accent),0.05)] border-[rgba(var(--accent),0.2)]">
        <CardContent className="py-12 text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center mb-6">
            <Package className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-xl font-semibold text-[rgb(var(--foreground))] mb-2">
            Your collection is empty
          </h2>
          <p className="text-[rgb(var(--muted-foreground))] mb-6 max-w-md mx-auto">
            Start by importing your MTG cards to track their value, get market insights, and
            receive personalized trading recommendations.
          </p>
          <div className="flex justify-center gap-4">
            <Link href="/inventory">
              <Button
                variant="primary"
                className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
              >
                <Package className="w-4 h-4 mr-2" />
                Import Cards
              </Button>
            </Link>
            <Link href="/cards">
              <Button variant="secondary">
                Browse Cards
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* Features overview */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6 text-center">
            <BarChart3 className="w-10 h-10 mx-auto text-amber-500 mb-4" />
            <h3 className="font-semibold text-[rgb(var(--foreground))] mb-2">
              Track Value
            </h3>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Monitor your collection&apos;s value across multiple marketplaces in real-time.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 text-center">
            <TrendingUp className="w-10 h-10 mx-auto text-green-500 mb-4" />
            <h3 className="font-semibold text-[rgb(var(--foreground))] mb-2">
              Price Alerts
            </h3>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Get notified when cards in your collection hit price targets.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 text-center">
            <Sparkles className="w-10 h-10 mx-auto text-purple-500 mb-4" />
            <h3 className="font-semibold text-[rgb(var(--foreground))] mb-2">
              AI Recommendations
            </h3>
            <p className="text-sm text-[rgb(var(--muted-foreground))]">
              Receive intelligent buy/sell suggestions based on market trends.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Mover item component for top movers section
interface MoverItemProps {
  name: string;
  setCode: string;
  price: number;
  changePct: number;
}

function MoverItem({ name, setCode, price, changePct }: MoverItemProps) {
  const isPositive = changePct >= 0;
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-[rgb(var(--secondary))]/50 hover:bg-[rgb(var(--secondary))] transition-colors">
      <div className="min-w-0 flex-1">
        <p className="font-medium text-[rgb(var(--foreground))] truncate">{name}</p>
        <p className="text-xs text-[rgb(var(--muted-foreground))] uppercase">{setCode}</p>
      </div>
      <div className="text-right ml-4">
        <p className="font-medium text-[rgb(var(--foreground))]">
          {formatCurrency(price)}
        </p>
        <p
          className={cn(
            'text-sm font-medium',
            isPositive ? 'text-green-500' : 'text-red-500'
          )}
        >
          {formatPercent(changePct)}
        </p>
      </div>
    </div>
  );
}

// Main dashboard content
function DashboardPageContent() {
  const { user } = useAuth();

  // Fetch inventory analytics
  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['inventory-analytics'],
    queryFn: getInventoryAnalytics,
    refetchInterval: 5 * 60 * 1000, // 5 minutes
  });

  // Fetch top movers from inventory
  const { data: topMovers, isLoading: moversLoading } = useQuery({
    queryKey: ['inventory-top-movers', '24h'],
    queryFn: () => getInventoryTopMovers('24h'),
    refetchInterval: 5 * 60 * 1000,
  });

  // Fetch recent recommendations
  const { data: recommendations, isLoading: recsLoading } = useQuery({
    queryKey: ['recommendations', { page: 1, pageSize: 5 }],
    queryFn: () => getRecommendations({ page: 1, pageSize: 5 }),
    refetchInterval: 15 * 60 * 1000,
  });

  const isLoading = analyticsLoading && !analytics;
  const username = user?.display_name || user?.username || 'Planeswalker';

  // Check if user has any inventory data
  const hasData = analytics && analytics.total_quantity > 0;

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (!hasData) {
    return <EmptyDashboard username={username} />;
  }

  // Calculate stats
  const portfolioValue = analytics?.total_current_value || 0;
  const profitLoss = analytics?.total_profit_loss || 0;
  const profitLossPct = analytics?.profit_loss_pct;
  const criticalAlerts = analytics?.critical_alerts || 0;
  const sellSignals = analytics?.sell_recommendations || 0;

  const profitTrend: 'up' | 'down' | 'neutral' =
    profitLoss > 0 ? 'up' : profitLoss < 0 ? 'down' : 'neutral';

  return (
    <div className="space-y-6 animate-in">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-bold text-[rgb(var(--foreground))]">
          Welcome back, {username}
        </h1>
        <p className="text-[rgb(var(--muted-foreground))]">
          Here&apos;s what&apos;s happening with your collection
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Portfolio Value"
          value={formatCurrency(portfolioValue)}
          icon={<DollarSign className="w-5 h-5" />}
        />
        <StatCard
          title="Profit/Loss"
          value={formatCurrency(profitLoss)}
          change={profitLossPct !== null && profitLossPct !== undefined ? formatPercent(profitLossPct) : undefined}
          trend={profitTrend}
          icon={profitTrend === 'up' ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
        />
        <StatCard
          title="Active Alerts"
          value={String(criticalAlerts + sellSignals)}
          icon={<Bell className="w-5 h-5" />}
        />
        <StatCard
          title="Total Cards"
          value={String(analytics?.total_quantity || 0)}
          change={`${analytics?.total_unique_cards || 0} unique`}
          icon={<Package className="w-5 h-5" />}
        />
      </div>

      {/* Main content grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Portfolio Chart Placeholder */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-[rgb(var(--accent))]" />
              Portfolio Value (30d)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 flex items-center justify-center border border-dashed border-[rgb(var(--border))] rounded-lg bg-[rgb(var(--secondary))]/30">
              <div className="text-center text-[rgb(var(--muted-foreground))]">
                <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>Chart coming soon</p>
                <p className="text-xs">View your inventory for detailed analytics</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Top Movers */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-500" />
                Top Movers Today
              </CardTitle>
              <Link
                href="/inventory"
                className="text-sm text-[rgb(var(--accent))] hover:underline flex items-center gap-1"
              >
                View all
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {moversLoading && !topMovers ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-[rgb(var(--secondary))]/50">
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                    <div className="space-y-2 text-right">
                      <Skeleton className="h-4 w-20" />
                      <Skeleton className="h-3 w-12 ml-auto" />
                    </div>
                  </div>
                ))}
              </div>
            ) : topMovers &&
              (topMovers.gainers.length > 0 || topMovers.losers.length > 0) ? (
              <div className="space-y-3">
                {/* Show top 2 gainers */}
                {topMovers.gainers.slice(0, 2).map((mover, idx) => (
                  <MoverItem
                    key={`gainer-${idx}`}
                    name={mover.cardName}
                    setCode={mover.setCode}
                    price={mover.currentPriceUsd}
                    changePct={mover.changePct}
                  />
                ))}
                {/* Show top 1 loser */}
                {topMovers.losers.slice(0, 1).map((mover, idx) => (
                  <MoverItem
                    key={`loser-${idx}`}
                    name={mover.cardName}
                    setCode={mover.setCode}
                    price={mover.currentPriceUsd}
                    changePct={mover.changePct}
                  />
                ))}
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
                <div className="text-center">
                  <TrendingUp className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p>No movers to show</p>
                  <p className="text-xs">Add cards to your inventory to track price changes</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recommendations */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-500" />
              Recent Recommendations
            </CardTitle>
            <Link
              href="/recommendations"
              className="text-sm text-[rgb(var(--accent))] hover:underline flex items-center gap-1"
            >
              View all
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          {recsLoading && !recommendations ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-[rgb(var(--secondary))]/50">
                  <Skeleton className="h-12 w-12 rounded" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                  <Skeleton className="h-6 w-16 rounded-full" />
                </div>
              ))}
            </div>
          ) : recommendations && recommendations.recommendations.length > 0 ? (
            <div className="space-y-3">
              {recommendations.recommendations.slice(0, 5).map((rec) => (
                <Link
                  key={rec.id}
                  href={`/cards/${rec.card_id}`}
                  className="flex items-center gap-4 p-3 rounded-lg bg-[rgb(var(--secondary))]/50 hover:bg-[rgb(var(--secondary))] transition-colors"
                >
                  {rec.card_image_url ? (
                    <img
                      src={rec.card_image_url}
                      alt={rec.card_name}
                      className="h-12 w-auto rounded"
                    />
                  ) : (
                    <div className="h-12 w-9 bg-[rgb(var(--muted))] rounded flex items-center justify-center">
                      <Package className="w-4 h-4 text-[rgb(var(--muted-foreground))]" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-[rgb(var(--foreground))] truncate">
                      {rec.card_name}
                    </p>
                    <p className="text-xs text-[rgb(var(--muted-foreground))] truncate">
                      {rec.rationale}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'px-3 py-1 rounded-full text-xs font-semibold',
                      rec.action === 'BUY'
                        ? 'bg-green-500/20 text-green-500'
                        : rec.action === 'SELL'
                          ? 'bg-red-500/20 text-red-500'
                          : 'bg-yellow-500/20 text-yellow-500'
                    )}
                  >
                    {rec.action}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="h-32 flex items-center justify-center text-[rgb(var(--muted-foreground))]">
              <div className="text-center">
                <Target className="w-10 h-10 mx-auto mb-2 opacity-50" />
                <p>No recommendations yet</p>
                <p className="text-xs">Recommendations are generated periodically based on market data</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardPageContent />
    </ProtectedRoute>
  );
}
